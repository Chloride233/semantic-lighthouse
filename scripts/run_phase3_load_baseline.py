"""Run an offline authenticated RAG load baseline at 1, 10, and 50 concurrency."""

from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from dataclasses import asdict, dataclass
import json
import platform
from pathlib import Path
import sys
import tempfile
import time

try:
    import resource
except ImportError:  # pragma: no cover - Windows compatibility.
    resource = None

import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from semantic_lighthouse.config import Settings, get_settings  # noqa: E402
from semantic_lighthouse.database import get_db  # noqa: E402
from semantic_lighthouse.main import create_app  # noqa: E402
from semantic_lighthouse.models import Base  # noqa: E402


CONCURRENCY_LEVELS = (1, 10, 50)


@dataclass(frozen=True)
class RequestResult:
    latency_ms: float
    status_code: int | None
    request_id: str
    error: str | None = None


@dataclass(frozen=True)
class ResourceSnapshot:
    user_cpu_seconds: float
    system_cpu_seconds: float
    process_peak_rss_mb: float | None


def nearest_rank(values: list[float], percentile: int) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, ((len(ordered) * percentile + 99) // 100) - 1)
    return ordered[index]


def _resource_snapshot() -> ResourceSnapshot:
    if resource is None:
        return ResourceSnapshot(time.process_time(), 0.0, None)
    usage = resource.getrusage(resource.RUSAGE_SELF)
    divisor = 1024 * 1024 if platform.system() == "Darwin" else 1024
    return ResourceSnapshot(usage.ru_utime, usage.ru_stime, usage.ru_maxrss / divisor)


def summarize_results(
    concurrency: int,
    results: list[RequestResult],
    elapsed_seconds: float,
    before: ResourceSnapshot,
    after: ResourceSnapshot,
) -> dict:
    latencies = [result.latency_ms for result in results]
    failures = [
        result
        for result in results
        if result.error is not None or result.status_code != 200
    ]
    status_counts = Counter(
        str(result.status_code) if result.status_code is not None else "exception"
        for result in results
    )
    return {
        "concurrency": concurrency,
        "requests": len(results),
        "successes": len(results) - len(failures),
        "errors": len(failures),
        "error_rate": round(len(failures) / len(results), 4) if results else 0.0,
        "throughput_rps": round(len(results) / elapsed_seconds, 2),
        "latency_ms": {
            "p50": round(nearest_rank(latencies, 50), 2),
            "p95": round(nearest_rank(latencies, 95), 2),
            "p99": round(nearest_rank(latencies, 99), 2),
            "min": round(min(latencies), 2) if latencies else 0.0,
            "max": round(max(latencies), 2) if latencies else 0.0,
        },
        "status_counts": dict(sorted(status_counts.items())),
        "resource": {
            "wall_seconds": round(elapsed_seconds, 3),
            "user_cpu_seconds": round(
                after.user_cpu_seconds - before.user_cpu_seconds, 3
            ),
            "system_cpu_seconds": round(
                after.system_cpu_seconds - before.system_cpu_seconds, 3
            ),
            "process_peak_rss_mb": (
                round(after.process_peak_rss_mb, 2)
                if after.process_peak_rss_mb is not None
                else None
            ),
        },
        "trace_samples": [asdict(result) for result in failures[:5]],
        "first_request_id": results[0].request_id if results else None,
    }


async def _request_once(
    client: httpx.AsyncClient,
    url: str,
    auth_headers: dict[str, str],
    request_id: str,
    semaphore: asyncio.Semaphore,
) -> RequestResult:
    async with semaphore:
        started_at = time.perf_counter()
        try:
            response = await client.post(
                url,
                json={"question": "What does the ontology connect?", "retrieval_method": "keyword"},
                headers={**auth_headers, "X-Request-ID": request_id},
            )
            latency_ms = (time.perf_counter() - started_at) * 1000
            echoed_request_id = response.headers.get("X-Request-ID")
            error = None
            if echoed_request_id != request_id:
                error = f"request ID mismatch: {echoed_request_id!r}"
            return RequestResult(latency_ms, response.status_code, request_id, error)
        except Exception as exc:
            latency_ms = (time.perf_counter() - started_at) * 1000
            return RequestResult(latency_ms, None, request_id, f"{type(exc).__name__}: {exc}")


async def run_scenario(
    client: httpx.AsyncClient,
    url: str,
    auth_headers: dict[str, str],
    concurrency: int,
    request_count: int,
) -> dict:
    semaphore = asyncio.Semaphore(concurrency)
    before = _resource_snapshot()
    started_at = time.perf_counter()
    results = await asyncio.gather(
        *(
            _request_once(
                client,
                url,
                auth_headers,
                f"phase3-c{concurrency}-r{index}",
                semaphore,
            )
            for index in range(request_count)
        )
    )
    elapsed_seconds = time.perf_counter() - started_at
    after = _resource_snapshot()
    return summarize_results(concurrency, results, elapsed_seconds, before, after)


def _require(response: httpx.Response, expected_status: int) -> dict:
    if response.status_code != expected_status:
        raise RuntimeError(
            f"setup request failed with HTTP {response.status_code}: {response.text[:300]}"
        )
    return response.json()


async def run_baseline(request_count: int) -> dict:
    with tempfile.TemporaryDirectory(prefix="semantic-lighthouse-phase3-") as temp_dir:
        database_path = Path(temp_dir) / "baseline.db"
        database_url = f"sqlite+pysqlite:///{database_path.as_posix()}"
        engine = create_engine(database_url)
        session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        Base.metadata.create_all(bind=engine)

        settings = Settings(
            database_url=database_url,
            jwt_secret_key="phase3-test-secret-key-at-least-32-bytes",
            knowledge_base_path=temp_dir,
            embedding_provider="fake",
            embedding_model="fake-embedding",
            embedding_dimension=8,
            chat_provider="fake",
            chat_model="fake-chat",
            rag_top_k=3,
        )
        app = create_app()

        def override_get_db():
            db = session_local()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_settings] = lambda: settings

        try:
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://phase3.local",
                timeout=30,
            ) as client:
                _require(
                    await client.post(
                        "/auth/register",
                        json={
                            "email": "phase3-load@example.com",
                            "password": "Passw0rd!",
                            "display_name": "Phase 3 Load",
                        },
                    ),
                    201,
                )
                login = _require(
                    await client.post(
                        "/auth/login",
                        json={"email": "phase3-load@example.com", "password": "Passw0rd!"},
                    ),
                    200,
                )
                auth_headers = {"Authorization": f"Bearer {login['access_token']}"}
                group = _require(
                    await client.post(
                        "/groups", json={"name": "Phase 3 Load"}, headers=auth_headers
                    ),
                    201,
                )
                group_id = group["id"]
                _require(
                    await client.post(
                        f"/groups/{group_id}/documents/upload",
                        files={
                            "file": (
                                "ontology.md",
                                b"# Ontology\n\nOntology connects business objects, data, and AI workflows.",
                                "text/markdown",
                            )
                        },
                        headers=auth_headers,
                    ),
                    201,
                )
                url = f"/groups/{group_id}/rag/answer"
                warmup = await client.post(
                    url,
                    json={"question": "Ontology", "retrieval_method": "keyword"},
                    headers=auth_headers,
                )
                _require(warmup, 200)

                scenarios = [
                    await run_scenario(
                        client, url, auth_headers, concurrency, request_count
                    )
                    for concurrency in CONCURRENCY_LEVELS
                ]
        finally:
            engine.dispose()

    return {
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "database": "temporary SQLite",
            "chat_provider": "fake",
            "embedding_provider": "fake",
            "transport": "httpx ASGITransport",
        },
        "scenarios": scenarios,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--requests-per-level", type=int, default=100)
    parser.add_argument(
        "--output", type=Path, default=Path(".tmp/phase3-load-baseline.json")
    )
    args = parser.parse_args()
    if args.requests_per_level < max(CONCURRENCY_LEVELS):
        parser.error("--requests-per-level must be at least 50")

    result = asyncio.run(run_baseline(args.requests_per_level))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
