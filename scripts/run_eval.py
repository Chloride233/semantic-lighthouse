r"""P3 Retrieval Eval Runner — standalone, zero real API keys required.

Usage:
    cd f:/semantic-lighthouse
    .venv/Scripts/python scripts/run_eval.py

Output: JSON report to stdout with Recall@3/5, no-result rate, missed, false positives.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from collections.abc import Generator
from pathlib import Path
from typing import Any
from unittest import mock

os.environ["JWT_SECRET_KEY"] = "eval-secret-key-at-least-32-bytes"

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from semantic_lighthouse.main import create_app
from semantic_lighthouse.database import get_db
from semantic_lighthouse.config import Settings, get_settings
from semantic_lighthouse.models import Base
import semantic_lighthouse.main as app_main
import semantic_lighthouse.routers.documents as documents_router

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "tests" / "eval" / "fixtures"
QUERIES_FILE = Path(__file__).resolve().parent.parent / "tests" / "eval" / "queries.json"
TOP_K = 5


def _temp_db() -> tuple[Any, sessionmaker]:
    fd, path = tempfile.mkstemp(suffix=".db", prefix="sl_eval_")
    os.close(fd)
    engine = create_engine(f"sqlite+pysqlite:///{path}")
    Base.metadata.create_all(bind=engine)
    maker = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return engine, maker


def _make_client(db_session: Session, tmp_dir: Path) -> TestClient:
    app = create_app()

    def _override_db() -> Generator[Session, None, None]:
        yield db_session

    def _override_settings() -> Settings:
        return Settings(
            database_url="sqlite+pysqlite:///:memory:",
            jwt_secret_key="eval-secret-key-at-least-32-bytes",
            cookie_secure=False,
            cookie_samesite="lax",
            knowledge_base_path=str(tmp_dir),
            embedding_provider="fake",
            embedding_model="fake-embedding",
            embedding_dimension=8,
            chat_provider="fake",
            chat_model="fake-chat",
            rag_top_k=TOP_K,
        )

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_settings] = _override_settings

    maker = sessionmaker(bind=db_session.get_bind(), autoflush=False, autocommit=False)
    with (
        mock.patch.object(app_main, "SessionLocal", maker),
        mock.patch.object(documents_router, "SessionLocal", maker),
    ):
        return TestClient(app)


def _register(client: TestClient, email: str) -> dict[str, str]:
    r = client.post("/auth/register", json={"email": email, "password": "Passw0rd!", "display_name": email.split("@")[0]})
    assert r.status_code == 201, f"register: {r.text}"
    login = client.post("/auth/login", json={"email": email, "password": "Passw0rd!"})
    assert login.status_code == 200, f"login: {login.text}"
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def _create_group(client: TestClient, headers: dict[str, str]) -> str:
    r = client.post("/groups", json={"name": "Eval Team"}, headers=headers)
    assert r.status_code == 201, f"create group: {r.text}"
    return r.json()["id"]


def _upload(client: TestClient, gid: str, headers: dict[str, str], filepath: Path) -> str:
    name = filepath.name
    content = filepath.read_bytes()
    r = client.post(
        f"/groups/{gid}/documents/upload",
        files={"file": (name, content, "text/markdown")},
        headers=headers,
    )
    assert r.status_code == 201, f"upload {name}: {r.status_code} {r.text}"
    return r.json()["id"]


def _run_search(client: TestClient, gid: str, headers: dict[str, str], query: str, method: str) -> list[dict[str, Any]]:
    """Run retrieval via the routes that mirror the RAG pipeline's actual logic.

    GET /search is simple ILIKE substring — not suitable for Chinese NL questions.
    We use GET /search/hybrid and vary keyword_weight to isolate retrieval strategies.
    """
    weights = {"keyword": 1.0, "semantic": 0.0, "hybrid": 0.3}
    kw = weights.get(method, 0.3)
    r = client.get(
        f"/groups/{gid}/documents/search/hybrid",
        params={"q": query, "keyword_weight": kw, "limit": TOP_K},
        headers=headers,
    )
    assert r.status_code == 200, f"search {method} '{query}': {r.status_code}"
    return r.json()


def _recall_at_k(results: list[dict[str, Any]], expected: set[str], k: int) -> tuple[bool, set[str], set[str]]:
    top_titles = {item["title"] for item in results[:k]}
    hit = expected & top_titles
    missed = expected - top_titles
    return len(hit) > 0, hit, missed


def run_eval() -> dict[str, Any]:
    t0 = time.monotonic()
    engine = None

    try:
        engine, _maker = _temp_db()
        session = _maker()
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            client = _make_client(session, tmp)
            headers = _register(client, "eval@example.com")
            gid = _create_group(client, headers)

            fixtures = sorted(FIXTURES_DIR.glob("*.md"))
            if not fixtures:
                raise SystemExit(f"No fixtures found in {FIXTURES_DIR}")

            for fp in fixtures:
                _upload(client, gid, headers, fp)

            queries = json.loads(QUERIES_FILE.read_text(encoding="utf-8"))

            methods = ["keyword", "semantic", "hybrid"]
            report: dict[str, Any] = {
                "corpus": {"document_count": len(fixtures), "query_count": len(queries)},
                "methods": {},
                "duration_ms": 0,
            }

            for method in methods:
                recall3 = 0
                recall5 = 0
                no_result = 0
                missed_queries: list[dict[str, Any]] = []
                false_positives: list[dict[str, Any]] = []
                per_query: list[dict[str, Any]] = []

                for q in queries:
                    expected = set(q["expected_document_titles"])
                    results = _run_search(client, gid, headers, q["query"], method)

                    if not results:
                        no_result += 1
                        if expected:
                            missed_queries.append({"id": q["id"], "query": q["query"], "expected": list(expected)})
                        per_query.append({"id": q["id"], "recall3": False, "recall5": False, "result_count": 0})
                        continue

                    r3, hit3, miss3 = _recall_at_k(results, expected, 3)
                    r5, hit5, miss5 = _recall_at_k(results, expected, 5)
                    if r3:
                        recall3 += 1
                    if r5:
                        recall5 += 1
                    if miss5:
                        missed_queries.append({
                            "id": q["id"], "query": q["query"],
                            "expected": list(expected), "missed": list(miss5),
                            "top5_titles": [r["title"] for r in results[:5]],
                        })
                    top5_titles = {r["title"] for r in results[:5]}
                    fp = top5_titles - expected
                    if fp:
                        false_positives.append({
                            "id": q["id"], "query": q["query"],
                            "expected": list(expected), "false_positives": list(fp),
                        })
                    per_query.append({
                        "id": q["id"], "recall3": r3, "recall5": r5,
                        "hit_titles": list(hit5), "result_count": len(results),
                    })

                total = len(queries)
                report["methods"][method] = {
                    "recall_at_3": round(recall3 / total, 3) if total else 0,
                    "recall_at_5": round(recall5 / total, 3) if total else 0,
                    "no_result_rate": round(no_result / total, 3) if total else 0,
                    "missed_queries": missed_queries,
                    "false_positives": false_positives[:10],
                    "per_query": per_query,
                }

            report["duration_ms"] = int((time.monotonic() - t0) * 1000)
            return report

    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    report = run_eval()
    print(json.dumps(report, ensure_ascii=False, indent=2))
