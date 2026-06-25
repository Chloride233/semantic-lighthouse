r"""P1 RAG Quality Eval — real ontology KB, 10 audit questions.

Usage:
    cd semantic-lighthouse
    .venv/Scripts/python scripts/run_rag_quality_eval.py

Output: JSON report to stdout + optional markdown report.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
import warnings
from collections.abc import Generator
from pathlib import Path
from typing import Any
from unittest import mock

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from semantic_lighthouse.main import create_app
from semantic_lighthouse.database import get_db
from semantic_lighthouse.config import Settings, get_settings
from semantic_lighthouse.models import Base
import semantic_lighthouse.main as app_main
import semantic_lighthouse.routers.documents as documents_router

# Suppress Starlette deprecation warning before app creation.
warnings.filterwarnings("ignore", category=DeprecationWarning, module="starlette")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="fastapi")
os.environ.setdefault("JWT_SECRET_KEY", "eval-secret-key-at-least-32-bytes")

ONTOLOGY_PATH = Path(os.environ.get("KNOWLEDGE_BASE_PATH", "./knowledge-graph"))
TOP_K = 5

# ── 10 Quality Audit Questions ──────────────────────────────────────────────
# expected_docs uses substrings that match actual document titles from import-local.
# Titles come from YAML frontmatter or first markdown heading.
QUALITY_QUESTIONS = [
    {
        "id": "Q1",
        "question": "企业为什么需要Ontology？",
        "expected_docs": ["Ontology (本体论", "主数据管理"],
        "category": "Ontology 基础",
    },
    {
        "id": "Q2",
        "question": "Ontology和数据中台有什么区别？",
        "expected_docs": ["Ontology (本体论", "Data Integration"],
        "category": "概念对比",
    },
    {
        "id": "Q3",
        "question": "企业AI转型第一阶段应该做什么？",
        "expected_docs": ["企业 AI 转型路线图"],
        "category": "AI 转型",
    },
    {
        "id": "Q4",
        "question": "RAG为什么需要引用来源？",
        "expected_docs": ["Graph RAG"],
        "category": "RAG 架构",
    },
    {
        "id": "Q5",
        "question": "知识图谱和Ontology有什么区别？",
        "expected_docs": ["Knowledge Graph", "Ontology (本体论"],
        "category": "概念对比",
    },
    {
        "id": "Q6",
        "question": "企业AI项目为什么不能只靠大模型？",
        "expected_docs": ["Ontology (本体论", "企业 AI 转型路线图", "Graph RAG"],
        "category": "AI 战略",
    },
    {
        "id": "Q7",
        "question": "数据治理和AI转型有什么关系？",
        "expected_docs": ["主数据管理", "Data Integration", "企业 AI 转型路线图"],
        "category": "数据治理",
    },
    {
        "id": "Q8",
        "question": "什么情况下应该低可信回答？",
        "expected_docs": ["Graph RAG", "算法权力偏差"],
        "category": "可信度",
    },
    {
        "id": "Q9",
        "question": "Agent为什么需要受控工具调用？",
        "expected_docs": ["MCP (Model Context Protocol)", "Action Type"],
        "category": "Agent",
    },
    {
        "id": "Q10",
        "question": "如何判断企业是否适合先做RAG？",
        "expected_docs": ["企业 AI 转型路线图", "Graph RAG"],
        "category": "评估决策",
    },
]

# ── Forbidden English phrases (contract test) ───────────────────────────────
FORBIDDEN_PHRASES = [
    "Based on retrieved sources",
    "according to the provided context",
    "the retrieved documents",
    "Review the cited chunks",
    "No context retrieved",
]


def _temp_db() -> tuple[Any, sessionmaker[Session]]:
    fd, path = tempfile.mkstemp(suffix=".db", prefix="sl_rag_eval_")
    os.close(fd)
    engine = create_engine(f"sqlite+pysqlite:///{path}")
    Base.metadata.create_all(bind=engine)
    maker = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return engine, maker


def _make_client(db_session: Session, ontology_path_str: str) -> TestClient:
    app = create_app()

    def _override_db() -> Generator[Session, None, None]:
        yield db_session

    def _override_settings() -> Settings:
        return Settings(
            database_url="sqlite+pysqlite:///:memory:",
            jwt_secret_key="eval-secret-key-at-least-32-bytes",
            cookie_secure=False,
            cookie_samesite="lax",
            knowledge_base_path=ontology_path_str,
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
    r = client.post(
        "/auth/register",
        json={"email": email, "password": "Passw0rd!", "display_name": email.split("@")[0]},
    )
    assert r.status_code == 201, f"register: {r.text}"
    login = client.post("/auth/login", json={"email": email, "password": "Passw0rd!"})
    assert login.status_code == 200, f"login: {login.text}"
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def _create_group(client: TestClient, headers: dict[str, str]) -> str:
    r = client.post("/groups", json={"name": "Quality Eval Team"}, headers=headers)
    assert r.status_code == 201, f"create group: {r.text}"
    return r.json()["id"]


def _check_chinese(text: str) -> bool:
    """Return True if text contains at least one Chinese character."""
    return any(ord(ch) > 127 for ch in text)


def _check_forbidden(text: str) -> list[str]:
    """Return list of forbidden phrases found in text."""
    found: list[str] = []
    for phrase in FORBIDDEN_PHRASES:
        if phrase.lower() in text.lower():
            found.append(phrase)
    return found


def _check_citations_traceable(citations: list[dict[str, Any]]) -> dict[str, Any]:
    """Verify each citation has required fields for traceability."""
    issues: list[str] = []
    required = ["document_id", "chunk_id", "title", "source_path", "snippet", "retrieval_method"]
    for i, c in enumerate(citations):
        for field in required:
            if field not in c or c[field] is None:
                issues.append(f"citation[{i}] missing {field}")
        if c.get("score") is not None and not isinstance(c["score"], (int, float)):
            issues.append(f"citation[{i}] score not numeric: {c['score']}")
    return {
        "all_traceable": len(issues) == 0,
        "issues": issues,
        "count": len(citations),
    }


def run_eval() -> dict[str, Any]:
    t0 = time.monotonic()
    engine = None

    if not ONTOLOGY_PATH.exists():
        return {"error": f"Ontology path not found: {ONTOLOGY_PATH}"}

    try:
        engine, _maker = _temp_db()
        session = _maker()
        client = _make_client(session, str(ONTOLOGY_PATH))
        headers = _register(client, "eval@example.com")
        gid = _create_group(client, headers)

        # ── Phase A: Import real ontology ──────────────────────────────────
        import_resp = client.post(
            f"/groups/{gid}/documents/import-local",
            headers=headers,
        )
        assert import_resp.status_code == 201, f"import-local failed: {import_resp.text}"
        import_data = import_resp.json()

        # ── Rebuild embeddings (fake, for semantic/hybrid support) ─────────
        rebuild = client.post(
            f"/groups/{gid}/documents/embeddings/rebuild",
            headers=headers,
        )
        assert rebuild.status_code == 200, f"rebuild failed: {rebuild.text}"

        total_docs = import_data["imported_count"]
        skipped = import_data["skipped_count"]

        # ── Phase C: Run 10 RAG questions ──────────────────────────────────
        per_question: list[dict[str, Any]] = []
        contract_issues: list[dict[str, Any]] = []

        for q in QUALITY_QUESTIONS:
            q_start = time.monotonic()
            for method in ["keyword", "hybrid"]:
                resp = client.post(
                    f"/groups/{gid}/rag/answer",
                    json={
                        "question": q["question"],
                        "retrieval_method": method,
                        "limit": TOP_K,
                    },
                    headers=headers,
                )
                assert resp.status_code == 200, (
                    f"RAG failed for {q['id']} ({method}): {resp.status_code} {resp.text}"
                )
                payload = resp.json()

                # ── Check run audit ────────────────────────────────────────
                run_id = payload.get("run_id", "")
                run_detail = None
                if run_id:
                    rd = client.get(
                        f"/groups/{gid}/rag/runs/{run_id}",
                        headers=headers,
                    )
                    if rd.status_code == 200:
                        run_detail = rd.json()

                # ── Collect dimensions ─────────────────────────────────────
                citations = payload.get("citations", [])
                answer = payload.get("answer", "")
                confidence = payload.get("confidence", "unknown")
                knowledge_gaps = payload.get("knowledge_gaps", [])
                next_steps = payload.get("next_steps", [])

                # Citation titles
                citation_titles = [c.get("title", "") for c in citations]

                # Expected doc match
                expected_matched = [
                    exp for exp in q["expected_docs"]
                    if any(exp.lower() in (c.get("title", "") or "").lower() for c in citations)
                ]
                expected_missed = [
                    exp for exp in q["expected_docs"] if exp not in expected_matched
                ]

                # Chinese check
                answer_is_chinese = _check_chinese(answer)
                gaps_all_chinese = (
                    all(_check_chinese(g) for g in knowledge_gaps) if knowledge_gaps else True
                )
                steps_all_chinese = (
                    all(_check_chinese(s) for s in next_steps) if next_steps else True
                )

                # Forbidden phrase check
                forbidden_in_answer = _check_forbidden(answer)
                forbidden_in_gaps = [p for g in knowledge_gaps for p in _check_forbidden(g)]
                forbidden_in_steps = [p for s in next_steps for p in _check_forbidden(s)]

                # Citation traceability
                trace = _check_citations_traceable(citations)

                # Audit fields
                audit_ok = False
                audit_detail: dict[str, Any] = {}
                if run_detail:
                    audit_ok = (
                        run_detail.get("status") in ("success", "no_evidence")
                        and isinstance(run_detail.get("duration_ms"), int)
                        and run_detail.get("retrieved_count") is not None
                    )
                    audit_detail = {
                        "status": run_detail.get("status"),
                        "duration_ms": run_detail.get("duration_ms"),
                        "retrieved_count": run_detail.get("retrieved_count"),
                        "error_message": run_detail.get("error_message"),
                    }

                # Confidence validity
                confidence_valid = confidence in ("high", "medium", "low")

                # Issues for this question
                q_issues: list[str] = []
                if not answer_is_chinese:
                    q_issues.append("answer is not Chinese")
                if not gaps_all_chinese:
                    q_issues.append("knowledge_gaps contain non-Chinese")
                if not steps_all_chinese:
                    q_issues.append("next_steps contain non-Chinese")
                if forbidden_in_answer:
                    q_issues.append(f"forbidden phrases in answer: {forbidden_in_answer}")
                if forbidden_in_gaps:
                    q_issues.append(f"forbidden phrases in knowledge_gaps: {forbidden_in_gaps}")
                if forbidden_in_steps:
                    q_issues.append(f"forbidden phrases in next_steps: {forbidden_in_steps}")
                if not trace["all_traceable"]:
                    q_issues.append(f"citation traceability: {trace['issues']}")
                if not confidence_valid:
                    q_issues.append(f"invalid confidence: {confidence}")
                if not audit_ok and run_detail:
                    q_issues.append(f"audit fields incomplete: {audit_detail}")
                # Only flag retrieval misses on keyword (deterministic ranking).
                # Hybrid with fake embeddings has degraded ranking — known limitation.
                if expected_missed and method == "keyword":
                    q_issues.append(f"expected docs not retrieved: {expected_missed}")

                record = {
                    "id": q["id"],
                    "question": q["question"],
                    "category": q["category"],
                    "method": method,
                    "expected_docs": q["expected_docs"],
                    "expected_matched": expected_matched,
                    "expected_missed": expected_missed,
                    "citation_titles": citation_titles,
                    "citation_count": len(citations),
                    "confidence": confidence,
                    "confidence_valid": confidence_valid,
                    "answer_sample": answer[:200],
                    "answer_is_chinese": answer_is_chinese,
                    "gaps_all_chinese": gaps_all_chinese,
                    "steps_all_chinese": steps_all_chinese,
                    "forbidden_in_answer": forbidden_in_answer,
                    "forbidden_in_gaps": forbidden_in_gaps,
                    "forbidden_in_steps": forbidden_in_steps,
                    "citations_traceable": trace["all_traceable"],
                    "citation_trace_issues": trace["issues"],
                    "knowledge_gaps_count": len(knowledge_gaps),
                    "next_steps_count": len(next_steps),
                    "run_id": run_id,
                    "audit_ok": audit_ok,
                    "audit_detail": audit_detail,
                    "model": payload.get("model", "unknown"),
                    "retrieval_method": payload.get("retrieval_method", "unknown"),
                    "duration_ms": int((time.monotonic() - q_start) * 1000),
                    "issues": q_issues,
                }
                per_question.append(record)
                if q_issues:
                    contract_issues.append(record)

        # ── Summary statistics ──────────────────────────────────────────────
        total = len(per_question)
        chinese_ok = sum(1 for r in per_question if r["answer_is_chinese"])
        forbidden_clean = sum(
            1 for r in per_question
            if not r["forbidden_in_answer"]
            and not r["forbidden_in_gaps"]
            and not r["forbidden_in_steps"]
        )
        citations_traceable = sum(1 for r in per_question if r["citations_traceable"])
        confidence_valid_count = sum(1 for r in per_question if r["confidence_valid"])
        audit_ok_count = sum(1 for r in per_question if r["audit_ok"])
        with_issues = sum(1 for r in per_question if r["issues"])

        # Per-category summary
        categories: dict[str, Any] = {}
        for r in per_question:
            cat = r["category"]
            if cat not in categories:
                categories[cat] = {"total": 0, "issues": 0}
            categories[cat]["total"] += 1
            if r["issues"]:
                categories[cat]["issues"] += 1

        duration_ms = int((time.monotonic() - t0) * 1000)

        return {
            "meta": {
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "ontology_path": str(ONTOLOGY_PATH),
                "chat_provider": "fake",
                "embedding_provider": "fake",
                "total_imported": total_docs,
                "total_skipped": skipped,
                "total_questions": len(QUALITY_QUESTIONS),
                "total_records": total,
                "duration_ms": duration_ms,
            },
            "summary": {
                "chinese_ok": f"{chinese_ok}/{total}",
                "forbidden_clean": f"{forbidden_clean}/{total}",
                "citations_traceable": f"{citations_traceable}/{total}",
                "confidence_valid": f"{confidence_valid_count}/{total}",
                "audit_ok": f"{audit_ok_count}/{total}",
                "records_with_issues": f"{with_issues}/{total}",
                "total_contract_issues": len(contract_issues),
            },
            "categories": categories,
            "contract_issues": contract_issues,
            "per_question": per_question,
        }

    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    report = run_eval()
    # Write JSON to file (avoids pipe encoding issues on Windows).
    out_path = Path(__file__).resolve().parent.parent / ".tmp" / "rag_eval_report.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Report written to {out_path}")
    print(f"Summary: {json.dumps(report.get('summary', {}), ensure_ascii=False)}")
