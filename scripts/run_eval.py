r"""P3 Retrieval Eval Runner — standalone, zero real API keys required.

Usage:
    cd f:/semantic-lighthouse
    .venv/Scripts/python scripts/run_eval.py
    .venv/Scripts/python scripts/run_eval.py --output .tmp/retrieval_eval.json --markdown .tmp/retrieval_eval.md

Output: JSON with Recall@3/5, MRR, Precision@5, no-result rate, per-method breakdown.
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import time
from collections.abc import Generator
from hashlib import sha256
from pathlib import Path
from typing import Any
from unittest import mock

os.environ["JWT_SECRET_KEY"] = "eval-secret-key-at-least-32-bytes"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from semantic_lighthouse.main import create_app
from semantic_lighthouse.database import get_db
from semantic_lighthouse.config import Settings, get_settings
from semantic_lighthouse.models import Base, DocumentChunk
import semantic_lighthouse.main as app_main
import semantic_lighthouse.routers.documents as documents_router
import semantic_lighthouse.services.embeddings as embeddings_service

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "tests" / "eval" / "fixtures"
QUERIES_FILE = Path(__file__).resolve().parent.parent / "tests" / "eval" / "queries.json"
TOP_K = 5
EVAL_EMBEDDING_DIMENSION = 256


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
            embedding_dimension=EVAL_EMBEDDING_DIMENSION,
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


def _run_rag(
    client: TestClient,
    gid: str,
    headers: dict[str, str],
    query: str,
    method: str,
) -> dict[str, Any]:
    response = client.post(
        f"/groups/{gid}/rag/answer",
        json={"question": query, "retrieval_method": method, "limit": TOP_K},
        headers=headers,
    )
    assert response.status_code == 200, f"rag {method} '{query}': {response.status_code} {response.text}"
    return response.json()


def _recall_at_k(results: list[dict[str, Any]], expected: set[str], k: int) -> tuple[bool, set[str], set[str]]:
    top_titles = {item["title"] for item in results[:k]}
    hit = expected & top_titles
    missed = expected - top_titles
    return len(hit) > 0, hit, missed


def _mrr(results: list[dict[str, Any]], expected: set[str]) -> float:
    """Mean Reciprocal Rank — rank of the first expected document in results."""
    if not expected:
        return 0.0
    for rank, item in enumerate(results, start=1):
        if item["title"] in expected:
            return 1.0 / rank
    return 0.0


def _precision_at_k(results: list[dict[str, Any]], expected: set[str], k: int) -> float:
    """Fraction of top-K results that are in the expected set."""
    if not results[:k]:
        return 0.0
    top_titles = {item["title"] for item in results[:k]}
    hits = len(expected & top_titles)
    return hits / min(k, len(results[:k]))


def _content_tokens(text: str) -> set[str]:
    """Return deterministic English words and CJK trigrams for overlap scoring."""
    normalized = text.casefold()
    tokens = set(re.findall(r"[a-z0-9][a-z0-9@._+-]*", normalized))
    for run in re.findall(r"[\u4e00-\u9fff]+", normalized):
        if len(run) < 3:
            tokens.add(run)
        else:
            tokens.update(run[index:index + 3] for index in range(len(run) - 2))
    return {token for token in tokens if token}


def _eval_embedding(text: str, dimension: int) -> list[float]:
    """Create a deterministic feature-hashing vector for offline comparison."""
    vector = [0.0] * dimension
    for token in _content_tokens(text):
        digest = sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dimension
        vector[index] += 1.0 if digest[4] % 2 == 0 else -1.0
    norm = sum(value * value for value in vector) ** 0.5
    return [value / norm for value in vector] if norm else vector


def _seed_eval_embeddings(db: Session) -> None:
    """Write deterministic vectors to the temporary evaluation corpus."""
    for chunk in db.query(DocumentChunk).all():
        chunk.embedding = _eval_embedding(chunk.content, EVAL_EMBEDDING_DIMENSION)
        chunk.embedding_model = "eval-feature-hash"
    db.commit()


def _faithfulness(answer: str, citations: list[dict[str, Any]]) -> float:
    """Measure answer-token coverage by returned citation snippets.

    This deterministic proxy is intentionally not presented as an LLM judge.
    It measures how much answer wording can be traced to the supplied evidence.
    """
    answer_tokens = _content_tokens(answer)
    if not answer_tokens:
        return 0.0
    evidence_tokens = _content_tokens(" ".join(citation.get("snippet", "") for citation in citations))
    return len(answer_tokens & evidence_tokens) / len(answer_tokens)


def _correct_refusal(response: dict[str, Any]) -> bool:
    return (
        not response.get("citations")
        and response.get("confidence") == "low"
        and response.get("model") == "local-evidence-gate"
    )


def run_eval() -> dict[str, Any]:
    t0 = time.monotonic()
    engine = None
    embedding_patch = mock.patch.object(embeddings_service, "_hash_embedding", _eval_embedding)
    embedding_patch.start()

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
            _seed_eval_embeddings(session)

            queries = json.loads(QUERIES_FILE.read_text(encoding="utf-8"))

            methods = ["keyword", "semantic", "hybrid"]
            answerable = [q for q in queries if not q.get("expected_refusal", False)]
            refusal_queries = [q for q in queries if q.get("expected_refusal", False)]
            report: dict[str, Any] = {
                "corpus": {"document_count": len(fixtures), "query_count": len(queries)},
                "methods": {},
                "rag_metrics": {},
                "comparison": {},
                "duration_ms": 0,
            }

            for method in methods:
                recall3 = 0
                recall5 = 0
                mrr_sum = 0.0
                precision5_sum = 0.0
                no_result = 0
                missed_queries: list[dict[str, Any]] = []
                false_positives: list[dict[str, Any]] = []
                per_query: list[dict[str, Any]] = []

                for q in answerable:
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
                    q_mrr = _mrr(results, expected)
                    q_p5 = _precision_at_k(results, expected, 5)
                    if r3:
                        recall3 += 1
                    if r5:
                        recall5 += 1
                    mrr_sum += q_mrr
                    precision5_sum += q_p5
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

                total = len(answerable)
                report["methods"][method] = {
                    "recall_at_3": round(recall3 / total, 3) if total else 0,
                    "recall_at_5": round(recall5 / total, 3) if total else 0,
                    "mrr": round(mrr_sum / total, 3) if total else 0,
                    "precision_at_5": round(precision5_sum / total, 3) if total else 0,
                    "no_result_rate": round(no_result / total, 3) if total else 0,
                    "missed_queries": missed_queries,
                    "false_positives": false_positives[:10],
                    "per_query": per_query,
                }

            ranking = sorted(
                methods,
                key=lambda name: (
                    report["methods"][name]["recall_at_5"],
                    report["methods"][name]["mrr"],
                    report["methods"][name]["precision_at_5"],
                ),
                reverse=True,
            )
            keyword = report["methods"]["keyword"]
            hybrid = report["methods"]["hybrid"]
            report["comparison"] = {
                "embedding": "deterministic 256-dimension English-word and CJK-trigram feature hash",
                "ranking": ranking,
                "best_method": ranking[0],
                "hybrid_vs_keyword": {
                    "recall_at_5_delta": round(hybrid["recall_at_5"] - keyword["recall_at_5"], 3),
                    "mrr_delta": round(hybrid["mrr"] - keyword["mrr"], 3),
                    "precision_at_5_delta": round(
                        hybrid["precision_at_5"] - keyword["precision_at_5"], 3
                    ),
                },
            }

            citation_hits = 0
            citation_total = 0
            faithfulness_scores: list[float] = []
            rag_per_query: list[dict[str, Any]] = []

            for q in answerable:
                response = _run_rag(client, gid, headers, q["query"], "hybrid")
                expected_titles = set(q["expected_document_titles"])
                citations = response.get("citations", [])
                correct = sum(1 for citation in citations if citation.get("title") in expected_titles)
                score = _faithfulness(response.get("answer", ""), citations)
                citation_hits += correct
                citation_total += len(citations)
                faithfulness_scores.append(score)
                rag_per_query.append({
                    "id": q["id"],
                    "citation_count": len(citations),
                    "correct_citations": correct,
                    "faithfulness": round(score, 3),
                })

            refusal_results: list[dict[str, Any]] = []
            for q in refusal_queries:
                response = _run_rag(client, gid, headers, q["query"], "keyword")
                correct = _correct_refusal(response)
                refusal_results.append({
                    "id": q["id"],
                    "correct": correct,
                    "citation_count": len(response.get("citations", [])),
                    "confidence": response.get("confidence"),
                    "model": response.get("model"),
                })

            report["rag_metrics"] = {
                "evaluation_method": "fake provider; deterministic citation-title and token-overlap scoring",
                "answerable_queries": len(answerable),
                "refusal_queries": len(refusal_queries),
                "citation_correctness": round(citation_hits / citation_total, 3) if citation_total else 0.0,
                "faithfulness": round(sum(faithfulness_scores) / len(faithfulness_scores), 3)
                if faithfulness_scores else 0.0,
                "refusal_accuracy": round(
                    sum(result["correct"] for result in refusal_results) / len(refusal_results), 3
                ) if refusal_results else 0.0,
                "per_query": rag_per_query,
                "refusal_results": refusal_results,
            }

            report["duration_ms"] = int((time.monotonic() - t0) * 1000)
            return report

    finally:
        embedding_patch.stop()
        if engine is not None:
            engine.dispose()


def _generate_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Retrieval Evaluation Report",
        "",
        f"**Corpus**: {report['corpus']['document_count']} documents, {report['corpus']['query_count']} queries",
        f"**Duration**: {report['duration_ms']} ms",
        "",
        "| Method | Recall@3 | Recall@5 | MRR | Precision@5 | No-Result |",
        "|--------|----------|----------|-----|-------------|-----------|",
    ]
    for m, data in report.get("methods", {}).items():
        lines.append(
            f"| {m} | {data['recall_at_3']} | {data['recall_at_5']} | "
            f"{data['mrr']} | {data['precision_at_5']} | {data['no_result_rate']} |"
        )
    rag = report.get("rag_metrics", {})
    comparison = report.get("comparison", {})
    lines += [
        "",
        "## Method Comparison",
        "",
        f"- Best method: {comparison.get('best_method', 'n/a')}",
        f"- Ranking: {' > '.join(comparison.get('ranking', []))}",
        f"- Embedding baseline: {comparison.get('embedding', 'n/a')}",
        f"- Hybrid vs keyword: {comparison.get('hybrid_vs_keyword', {})}",
        "",
        "## RAG Grounding Metrics",
        "",
        f"- Citation correctness: {rag.get('citation_correctness', 0)}",
        f"- Faithfulness (deterministic answer-token coverage): {rag.get('faithfulness', 0)}",
        f"- Refusal accuracy: {rag.get('refusal_accuracy', 0)}",
        f"- Answerable / refusal queries: {rag.get('answerable_queries', 0)} / {rag.get('refusal_queries', 0)}",
        "",
        "**Known limitations**: vector search uses a deterministic lexical feature hash, not a neural semantic model. ",
        "Faithfulness is a deterministic token-overlap proxy, not an LLM-as-judge score. ",
        "Real-provider evaluation remains separate from this offline baseline.",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="P3 Retrieval Evaluation Runner")
    p.add_argument("--output", help="Write JSON report to file")
    p.add_argument("--markdown", help="Write Markdown report to file")
    args = p.parse_args()

    report = run_eval()

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"JSON report → {args.output}")

    if args.markdown:
        md = _generate_markdown(report)
        Path(args.markdown).parent.mkdir(parents=True, exist_ok=True)
        Path(args.markdown).write_text(md, encoding="utf-8")
        print(f"Markdown report → {args.markdown}")

    if not args.output and not args.markdown:
        print(json.dumps(report, ensure_ascii=False, indent=2))
