from pathlib import Path

from fastapi.testclient import TestClient

from conftest import register_and_login
from semantic_lighthouse.config import Settings, get_settings


def _settings(path: Path, chat_provider: str = "fake", embedding_provider: str = "fake") -> Settings:
    return Settings(
        database_url="sqlite+pysqlite:///:memory:",
        jwt_secret_key="test-secret-key-at-least-32-bytes",
        cookie_secure=False,
        cookie_samesite="lax",
        knowledge_base_path=str(path),
        embedding_provider=embedding_provider,
        embedding_model="fake-embedding",
        embedding_dimension=8,
        chat_provider=chat_provider,
        chat_model="fake-chat",
        rag_top_k=3,
    )


def _override_settings(client: TestClient, settings: Settings) -> None:
    def override() -> Settings:
        return settings

    client.app.dependency_overrides[get_settings] = override


def _create_group(client: TestClient, headers: dict[str, str], name: str = "Team") -> str:
    response = client.post("/groups", json={"name": name}, headers=headers)
    assert response.status_code == 201
    return response.json()["id"]


def _join_group(client: TestClient, group_id: str, owner_headers: dict[str, str], member_headers: dict[str, str]) -> None:
    invite = client.post(f"/groups/{group_id}/invites", headers=owner_headers)
    assert invite.status_code == 201
    joined = client.post(
        "/groups/join-by-invite",
        json={"invite_code": invite.json()["invite_code"]},
        headers=member_headers,
    )
    assert joined.status_code == 200


def _upload(client: TestClient, group_id: str, headers: dict[str, str], name: str, text: str) -> str:
    response = client.post(
        f"/groups/{group_id}/documents/upload",
        files={"file": (name, text.encode("utf-8"), "text/markdown")},
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_member_can_get_rag_answer_with_keyword_citations(client, tmp_path):
    _, _, owner_headers = register_and_login(client, "owner@example.com")
    _, _, member_headers = register_and_login(client, "member@example.com")
    group_id = _create_group(client, owner_headers)
    _join_group(client, group_id, owner_headers, member_headers)
    _override_settings(client, _settings(tmp_path))
    document_id = _upload(
        client,
        group_id,
        owner_headers,
        "ontology.md",
        """---
title: Enterprise Ontology
entityType: Concept
source: personal-analysis
status: reviewed
---

# Ontology

Ontology connects business objects, data, and AI workflows.
""",
    )

    response = client.post(
        f"/groups/{group_id}/rag/answer",
        json={"question": "Ontology", "retrieval_method": "keyword"},
        headers=member_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["question"] == "Ontology"
    assert payload["retrieval_method"] == "keyword"
    assert payload["model"] == "fake-chat"
    assert payload["citations"][0]["document_id"] == document_id
    assert payload["citations"][0]["retrieval_method"] == "keyword"
    assert payload["citations"][0]["entity_type"] == "Concept"
    assert payload["confidence"] in {"high", "medium"}


def test_fake_rag_answer_does_not_expose_prompt_text(client, tmp_path):
    _, _, owner_headers = register_and_login(client, "owner@example.com")
    group_id = _create_group(client, owner_headers)
    _override_settings(client, _settings(tmp_path))
    _upload(
        client,
        group_id,
        owner_headers,
        "roadmap.md",
        "# 企业 AI 转型路线图\n\n企业需要 Ontology 来统一业务语义、数据资产、权限和 AI 工作流。",
    )

    response = client.post(
        f"/groups/{group_id}/rag/answer",
        json={"question": "企业为什么需要Ontology?", "retrieval_method": "keyword"},
        headers=owner_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert "Based on" not in payload["answer"]
    assert "retrieved source" not in payload["answer"]
    assert "企业需要 Ontology" in payload["answer"]
    assert all("Review the cited chunks" not in step for step in payload["next_steps"])
    assert payload["next_steps"]


def test_rag_answer_can_use_semantic_retrieval(client, tmp_path):
    _, _, owner_headers = register_and_login(client, "owner@example.com")
    group_id = _create_group(client, owner_headers)
    _override_settings(client, _settings(tmp_path))
    _upload(
        client,
        group_id,
        owner_headers,
        "roadmap.md",
        "# AI Roadmap\n\nSemantic retrieval supports enterprise AI transformation.",
    )
    rebuild = client.post(f"/groups/{group_id}/documents/embeddings/rebuild", headers=owner_headers)
    assert rebuild.status_code == 200

    response = client.post(
        f"/groups/{group_id}/rag/answer",
        json={"question": "enterprise transformation", "retrieval_method": "semantic"},
        headers=owner_headers,
    )

    assert response.status_code == 200
    result = response.json()
    assert result["retrieval_method"] == "semantic"
    assert result["citations"][0]["retrieval_method"] == "semantic"
    assert result["citations"][0]["score"] <= 1.0


def test_non_member_cannot_get_rag_answer(client, tmp_path):
    _, _, owner_headers = register_and_login(client, "owner@example.com")
    _, _, outsider_headers = register_and_login(client, "outsider@example.com")
    group_id = _create_group(client, owner_headers)
    _override_settings(client, _settings(tmp_path))

    response = client.post(
        f"/groups/{group_id}/rag/answer",
        json={"question": "Ontology"},
        headers=outsider_headers,
    )

    assert response.status_code == 403


def test_rag_answer_is_filtered_by_group_id(client, tmp_path):
    _, _, owner_headers = register_and_login(client, "owner@example.com")
    group_a = _create_group(client, owner_headers, "A")
    group_b = _create_group(client, owner_headers, "B")
    _override_settings(client, _settings(tmp_path))
    _upload(client, group_a, owner_headers, "a.md", "# A\n\nshared answer belongs to group A")
    _upload(client, group_b, owner_headers, "b.md", "# B\n\nshared answer belongs to group B")

    response = client.post(
        f"/groups/{group_a}/rag/answer",
        json={"question": "shared", "retrieval_method": "keyword"},
        headers=owner_headers,
    )

    assert response.status_code == 200
    citations = response.json()["citations"]
    assert len(citations) == 1
    assert citations[0]["source_path"] == "upload:a.md"


def test_missing_deepseek_api_key_returns_clear_error(client, tmp_path):
    _, _, owner_headers = register_and_login(client, "owner@example.com")
    group_id = _create_group(client, owner_headers)
    _override_settings(client, _settings(tmp_path, chat_provider="deepseek"))
    _upload(client, group_id, owner_headers, "ontology.md", "# Ontology\n\nOntology content.")

    response = client.post(
        f"/groups/{group_id}/rag/answer",
        json={"question": "Ontology", "retrieval_method": "keyword"},
        headers=owner_headers,
    )

    assert response.status_code == 502
    assert "DEEPSEEK_API_KEY" in response.json()["detail"]


def test_no_retrieved_evidence_returns_low_confidence_without_calling_chat_provider(client, tmp_path):
    _, _, owner_headers = register_and_login(client, "owner@example.com")
    group_id = _create_group(client, owner_headers)
    _override_settings(client, _settings(tmp_path, chat_provider="deepseek"))
    _upload(client, group_id, owner_headers, "ontology.md", "# Ontology\n\nOntology content.")

    response = client.post(
        f"/groups/{group_id}/rag/answer",
        json={"question": "unmatched customer risk", "retrieval_method": "keyword"},
        headers=owner_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["confidence"] == "low"
    assert payload["citations"] == []
    assert payload["model"] == "local-evidence-gate"
    assert payload["knowledge_gaps"]


def test_keyword_rag_extracts_terms_from_long_customer_question(client, tmp_path):
    _, _, owner_headers = register_and_login(client, "owner@example.com")
    group_id = _create_group(client, owner_headers)
    _override_settings(client, _settings(tmp_path))
    _upload(
        client,
        group_id,
        owner_headers,
        "ontology.md",
        "# Ontology\n\nOntology helps connect data platforms with AI workflows.",
    )

    response = client.post(
        f"/groups/{group_id}/rag/answer",
        json={"question": "我们已经有数据中台，为什么还需要 Ontology？", "retrieval_method": "keyword"},
        headers=owner_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["citations"][0]["title"] == "Ontology"
    assert payload["model"] == "fake-chat"


def test_rag_answer_is_persisted_and_can_be_replayed(client, tmp_path):
    _, _, owner_headers = register_and_login(client, "owner@example.com")
    group_id = _create_group(client, owner_headers)
    _override_settings(client, _settings(tmp_path))
    _upload(
        client,
        group_id,
        owner_headers,
        "ontology.md",
        "# Ontology\n\nOntology helps connect business objects and AI workflows.",
    )

    answer = client.post(
        f"/groups/{group_id}/rag/answer",
        json={"question": "Ontology", "retrieval_method": "keyword"},
        headers=owner_headers,
    )
    run_id = answer.json()["run_id"]
    runs = client.get(f"/groups/{group_id}/rag/runs", headers=owner_headers)
    detail = client.get(f"/groups/{group_id}/rag/runs/{run_id}", headers=owner_headers)

    assert answer.status_code == 200
    assert run_id
    # Response includes confidence_reason
    answer_payload = answer.json()
    assert "confidence_reason" in answer_payload
    assert len(answer_payload["confidence_reason"]) > 0
    assert runs.status_code == 200
    assert runs.json()[0]["id"] == run_id
    assert runs.json()[0]["citation_count"] == 1
    assert detail.status_code == 200
    detail_payload = detail.json()
    assert detail_payload["id"] == run_id
    assert detail_payload["question"] == "Ontology"
    assert detail_payload["citations"][0]["title"] == "Ontology"
    # Detail also includes confidence_reason
    assert "confidence_reason" in detail_payload
    assert len(detail_payload["confidence_reason"]) > 0


def test_non_member_cannot_read_rag_run_history(client, tmp_path):
    _, _, owner_headers = register_and_login(client, "owner@example.com")
    _, _, outsider_headers = register_and_login(client, "outsider@example.com")
    group_id = _create_group(client, owner_headers)
    _override_settings(client, _settings(tmp_path))
    _upload(client, group_id, owner_headers, "ontology.md", "# Ontology\n\nOntology content.")
    answer = client.post(
        f"/groups/{group_id}/rag/answer",
        json={"question": "Ontology", "retrieval_method": "keyword"},
        headers=owner_headers,
    )
    run_id = answer.json()["run_id"]

    runs = client.get(f"/groups/{group_id}/rag/runs", headers=outsider_headers)
    detail = client.get(f"/groups/{group_id}/rag/runs/{run_id}", headers=outsider_headers)

    assert runs.status_code == 403
    assert detail.status_code == 403


# ── citation sanitization + confidence override tests ────────────────────


def test_sanitize_removes_out_of_range_refs():
    from semantic_lighthouse.schemas import RagCitation
    from semantic_lighthouse.services.chat import sanitize_references

    citations = [
        RagCitation(document_id="a", chunk_id="c1", title="T1", source_path="s", file_name="f",
                     chunk_index=0, heading_path=None, snippet="s1", retrieval_method="hybrid"),
        RagCitation(document_id="a", chunk_id="c2", title="T2", source_path="s", file_name="f",
                     chunk_index=1, heading_path=None, snippet="s2", retrieval_method="hybrid"),
    ]
    result = sanitize_references("See [1] and [5] and [0] for details.", citations)
    assert "[1]" in result
    assert "[5]" not in result
    assert "[0]" not in result
    assert "(source unavailable)" in result


def test_sanitize_keeps_all_valid_refs():
    from semantic_lighthouse.schemas import RagCitation
    from semantic_lighthouse.services.chat import sanitize_references

    citations = [
        RagCitation(document_id="a", chunk_id="c1", title="T1", source_path="s", file_name="f",
                     chunk_index=0, heading_path=None, snippet="s1", retrieval_method="keyword"),
    ]
    result = sanitize_references("Only source [1] is valid.", citations)
    assert result == "Only source [1] is valid."


def test_sanitize_no_op_when_no_refs():
    from semantic_lighthouse.services.chat import sanitize_references

    result = sanitize_references("Just an answer with no citations.", [])
    assert result == "Just an answer with no citations."


def test_adjusted_confidence_capped_medium_for_single_citation():
    from semantic_lighthouse.schemas import RagCitation
    from semantic_lighthouse.services.chat import adjusted_confidence

    citations = [
        RagCitation(document_id="a", chunk_id="c1", title="T", source_path="s", file_name="f",
                     chunk_index=0, heading_path=None, snippet="s", score=0.9, retrieval_method="hybrid"),
    ]
    conf, reason = adjusted_confidence("high", citations)
    assert conf == "medium"
    assert "仅有一条" in reason


def test_adjusted_confidence_low_for_weak_scores():
    from semantic_lighthouse.schemas import RagCitation
    from semantic_lighthouse.services.chat import adjusted_confidence

    citations = [
        RagCitation(document_id="a", chunk_id="c1", title="T1", source_path="s", file_name="f",
                     chunk_index=0, heading_path=None, snippet="s1", score=0.1, retrieval_method="hybrid"),
        RagCitation(document_id="a", chunk_id="c2", title="T2", source_path="s", file_name="f",
                     chunk_index=1, heading_path=None, snippet="s2", score=0.2, retrieval_method="hybrid"),
    ]
    conf, reason = adjusted_confidence("high", citations)
    assert conf == "low"
    assert "匹配分数" in reason and "0.3" in reason


def test_adjusted_confidence_requires_multi_document_for_high():
    """Two strong citations from the SAME document → cannot reach high."""
    from semantic_lighthouse.schemas import RagCitation
    from semantic_lighthouse.services.chat import adjusted_confidence

    citations = [
        RagCitation(document_id="a", chunk_id="c1", title="T1", source_path="s", file_name="f",
                     chunk_index=0, heading_path=None, snippet="s1", score=0.9, retrieval_method="hybrid"),
        RagCitation(document_id="a", chunk_id="c2", title="T2", source_path="s", file_name="f",
                     chunk_index=1, heading_path=None, snippet="s2", score=0.8, retrieval_method="hybrid"),
    ]
    conf, reason = adjusted_confidence("high", citations)
    assert conf == "medium"
    assert "同一份文档" in reason


def test_adjusted_confidence_high_for_multi_document_strong_scores():
    """≥2 different documents with strong scores → high is allowed."""
    from semantic_lighthouse.schemas import RagCitation
    from semantic_lighthouse.services.chat import adjusted_confidence

    citations = [
        RagCitation(document_id="doc-a", chunk_id="c1", title="Doc A", source_path="s", file_name="f",
                     chunk_index=0, heading_path=None, snippet="s1", score=0.9, retrieval_method="hybrid",
                     status="reviewed"),
        RagCitation(document_id="doc-b", chunk_id="c2", title="Doc B", source_path="s", file_name="f",
                     chunk_index=0, heading_path=None, snippet="s2", score=0.8, retrieval_method="hybrid",
                     status="reviewed"),
    ]
    conf, reason = adjusted_confidence("high", citations)
    assert conf == "high"
    assert "不同文档" in reason


def test_adjusted_confidence_draft_sources_downgrade():
    """>50% citations from draft/unknown → confidence downgraded by 1 level."""
    from semantic_lighthouse.schemas import RagCitation
    from semantic_lighthouse.services.chat import adjusted_confidence

    citations = [
        RagCitation(document_id="doc-a", chunk_id="c1", title="T1", source_path="s", file_name="f",
                     chunk_index=0, heading_path=None, snippet="s1", score=0.9, retrieval_method="hybrid",
                     status="draft"),
        RagCitation(document_id="doc-b", chunk_id="c2", title="T2", source_path="s", file_name="f",
                     chunk_index=0, heading_path=None, snippet="s2", score=0.8, retrieval_method="hybrid",
                     status="draft"),
        RagCitation(document_id="doc-c", chunk_id="c3", title="T3", source_path="s", file_name="f",
                     chunk_index=0, heading_path=None, snippet="s3", score=0.7, retrieval_method="hybrid",
                     status="reviewed"),
    ]
    conf, reason = adjusted_confidence("high", citations)
    # 2/3 are draft → downgrade from high to medium
    assert conf == "medium"
    assert "成熟度" in reason


def test_adjusted_confidence_zero_citations_has_reason():
    """0 citations → low confidence with descriptive Chinese reason."""
    from semantic_lighthouse.services.chat import adjusted_confidence

    conf, reason = adjusted_confidence("high", [])
    assert conf == "low"
    assert "未检索到" in reason
    assert len(reason) > 10


# ── output contract tests ─────────────────────────────────────────────────


def test_no_evidence_response_is_fully_chinese():
    from semantic_lighthouse.routers.rag import _no_evidence_response

    response = _no_evidence_response("Ontology 是什么？", "keyword")
    payload = response.model_dump()

    forbidden = [
        "Based on", "retrieved source", "provided context",
        "according to", "Review the cited", "No context",
    ]
    for field in ("answer",):
        for phrase in forbidden:
            assert phrase.lower() not in payload[field].lower(), (
                f"English phrase '{phrase}' leaked into {field}: {payload[field]}"
            )
    for field in ("knowledge_gaps", "next_steps"):
        for item in payload[field]:
            for phrase in forbidden:
                assert phrase.lower() not in item.lower(), (
                    f"English phrase '{phrase}' leaked into {field}: {item}"
                )
    assert payload["confidence"] == "low"
    assert payload["model"] == "local-evidence-gate"
    assert payload["citations"] == []


def test_fake_answer_with_english_docs_produces_chinese_output(client, tmp_path):
    _, _, owner_headers = register_and_login(client, "owner@example.com")
    group_id = _create_group(client, owner_headers)
    _override_settings(client, _settings(tmp_path))
    _upload(
        client,
        group_id,
        owner_headers,
        "english-report.md",
        (
            "# Enterprise AI Report\n\n"
            "The enterprise data platform requires a semantic layer for AI readiness. "
            "Without ontology, LLMs operate on raw schema names and miss business context."
        ),
    )

    response = client.post(
        f"/groups/{group_id}/rag/answer",
        json={"question": "Why does enterprise need semantic layer?", "retrieval_method": "keyword"},
        headers=owner_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert any(ord(ch) > 127 for ch in payload["answer"]), (
        f"answer contains no Chinese characters: {payload['answer'][:120]}"
    )
    for gap in payload["knowledge_gaps"]:
        assert any(ord(ch) > 127 for ch in gap), (
            f"knowledge_gap contains no Chinese: {gap}"
        )
    for step in payload["next_steps"]:
        assert any(ord(ch) > 127 for ch in step), (
            f"next_step contains no Chinese: {step}"
        )


def test_system_prompt_english_phrases_not_leaked(client, tmp_path):
    _, _, owner_headers = register_and_login(client, "owner@example.com")
    group_id = _create_group(client, owner_headers)
    _override_settings(client, _settings(tmp_path))
    _upload(
        client,
        group_id,
        owner_headers,
        "roadmap.md",
        "# 企业 AI 转型路线图\n\n企业需要 Ontology 来统一业务语义。",
    )

    response = client.post(
        f"/groups/{group_id}/rag/answer",
        json={"question": "企业如何规划AI转型？", "retrieval_method": "keyword"},
        headers=owner_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    forbidden_phrases = [
        "Based on retrieved sources",
        "according to the provided context",
        "the retrieved documents",
        "Review the cited chunks",
        "No context retrieved",
    ]
    for field in ("answer", "knowledge_gaps", "next_steps"):
        items = payload[field] if isinstance(payload[field], list) else [payload[field]]
        for item in items:
            for phrase in forbidden_phrases:
                assert phrase.lower() not in item.lower(), (
                    f"'{phrase}' leaked into {field}: {item}"
                )


# ── audit trail tests ──────────────────────────────────────────────────────


def test_rag_run_includes_audit_fields(client, tmp_path):
    """Success path: detail response includes status, duration, retrieved_count."""
    _, _, owner_headers = register_and_login(client, "owner@example.com")
    group_id = _create_group(client, owner_headers)
    _override_settings(client, _settings(tmp_path))
    _upload(
        client,
        group_id,
        owner_headers,
        "ontology.md",
        "# Ontology\n\nOntology helps connect business objects and AI workflows.",
    )

    answer = client.post(
        f"/groups/{group_id}/rag/answer",
        json={"question": "Ontology 是什么？", "retrieval_method": "keyword"},
        headers=owner_headers,
    )
    assert answer.status_code == 200
    run_id = answer.json()["run_id"]

    detail = client.get(f"/groups/{group_id}/rag/runs/{run_id}", headers=owner_headers)
    assert detail.status_code == 200
    d = detail.json()
    assert d["status"] == "success"
    assert isinstance(d["duration_ms"], int) and d["duration_ms"] > 0
    assert d["retrieved_count"] is not None and d["retrieved_count"] >= len(d["citations"])
    assert d["error_message"] is None

    # Summary also includes audit fields
    runs = client.get(f"/groups/{group_id}/rag/runs", headers=owner_headers)
    assert runs.status_code == 200
    s = runs.json()[0]
    assert s["status"] == "success"
    assert isinstance(s["duration_ms"], int)


def test_failed_rag_run_is_persisted_and_isolated(client, tmp_path):
    """Failed LLM calls must leave an audit record with error_message."""
    _, _, owner_headers = register_and_login(client, "owner@example.com")
    _, _, outsider_headers = register_and_login(client, "outsider@example.com")
    group_id = _create_group(client, owner_headers)
    # deepseek provider without API key → ChatError on LLM call
    _override_settings(client, _settings(tmp_path, chat_provider="deepseek"))
    _upload(client, group_id, owner_headers, "ontology.md", "# Ontology\n\nOntology content.")

    response = client.post(
        f"/groups/{group_id}/rag/answer",
        json={"question": "Ontology", "retrieval_method": "keyword"},
        headers=owner_headers,
    )
    assert response.status_code == 502
    assert "DEEPSEEK_API_KEY" in response.json()["detail"]

    # Failure must be in the run history for the owner
    runs = client.get(f"/groups/{group_id}/rag/runs", headers=owner_headers)
    assert runs.status_code == 200
    assert len(runs.json()) >= 1
    failed = runs.json()[0]
    assert failed["status"] == "error"
    assert failed["citation_count"] >= 1  # retrieved citations are preserved

    detail = client.get(
        f"/groups/{group_id}/rag/runs/{failed['id']}", headers=owner_headers,
    )
    assert detail.status_code == 200
    d = detail.json()
    assert d["status"] == "error"
    assert d["error_message"] and "DEEPSEEK_API_KEY" in d["error_message"]
    assert d["confidence"] == "low"
    assert d["model"] == "error"
    assert isinstance(d["duration_ms"], int) and d["duration_ms"] > 0
    assert d["retrieved_count"] is not None and d["retrieved_count"] >= 1

    # Non-member cannot read the failed run
    runs_out = client.get(f"/groups/{group_id}/rag/runs", headers=outsider_headers)
    assert runs_out.status_code == 403


def test_no_evidence_run_has_correct_audit_status(client, tmp_path):
    """No-evidence path should set status=no_evidence with duration and retrieved_count."""
    _, _, owner_headers = register_and_login(client, "owner@example.com")
    group_id = _create_group(client, owner_headers)
    _override_settings(client, _settings(tmp_path, chat_provider="deepseek"))
    _upload(client, group_id, owner_headers, "ontology.md", "# Ontology\n\nOntology content.")

    response = client.post(
        f"/groups/{group_id}/rag/answer",
        json={"question": "unmatched query term", "retrieval_method": "keyword"},
        headers=owner_headers,
    )
    assert response.status_code == 200
    run_id = response.json()["run_id"]

    detail = client.get(f"/groups/{group_id}/rag/runs/{run_id}", headers=owner_headers)
    assert detail.status_code == 200
    d = detail.json()
    assert d["status"] == "no_evidence"
    assert d["model"] == "local-evidence-gate"
    assert isinstance(d["duration_ms"], int) and d["duration_ms"] > 0
    assert d["retrieved_count"] == 0
    assert d["error_message"] is None


# ── evidence_quality tests ────────────────────────────────────────────────


def test_evidence_quality_zero_citations():
    from semantic_lighthouse.services.chat import compute_evidence_quality

    eq = compute_evidence_quality([])
    assert eq.retrieval_coverage == "none"
    assert eq.citation_diversity == "none"
    assert eq.score_distribution == "unknown"
    assert len(eq.summary) > 10
    assert "未检索到" in eq.summary


def test_evidence_quality_single_citation_low_diversity():
    from semantic_lighthouse.schemas import RagCitation
    from semantic_lighthouse.services.chat import compute_evidence_quality

    citations = [
        RagCitation(document_id="a", chunk_id="c1", title="T", source_path="s", file_name="f",
                     chunk_index=0, heading_path=None, snippet="s", score=0.9,
                     retrieval_method="hybrid", status="reviewed"),
    ]
    eq = compute_evidence_quality(citations)
    assert eq.retrieval_coverage == "weak"
    assert eq.citation_diversity == "low"
    assert eq.score_distribution == "strong"


def test_evidence_quality_same_doc_low_diversity():
    from semantic_lighthouse.schemas import RagCitation
    from semantic_lighthouse.services.chat import compute_evidence_quality

    citations = [
        RagCitation(document_id="a", chunk_id="c1", title="T1", source_path="s", file_name="f",
                     chunk_index=0, heading_path=None, snippet="s1", score=0.8,
                     retrieval_method="hybrid", status="reviewed"),
        RagCitation(document_id="a", chunk_id="c2", title="T2", source_path="s", file_name="f",
                     chunk_index=1, heading_path=None, snippet="s2", score=0.7,
                     retrieval_method="hybrid", status="reviewed"),
        RagCitation(document_id="a", chunk_id="c3", title="T3", source_path="s", file_name="f",
                     chunk_index=2, heading_path=None, snippet="s3", score=0.6,
                     retrieval_method="hybrid", status="reviewed"),
    ]
    eq = compute_evidence_quality(citations)
    assert eq.citation_diversity == "low"  # same doc
    assert eq.retrieval_coverage == "partial"  # 3 citations


def test_evidence_quality_multi_doc_high_diversity():
    from semantic_lighthouse.schemas import RagCitation
    from semantic_lighthouse.services.chat import compute_evidence_quality

    citations = [
        RagCitation(document_id="doc-a", chunk_id="c1", title="Doc A", source_path="s", file_name="f",
                     chunk_index=0, heading_path=None, snippet="s1", score=0.9,
                     retrieval_method="hybrid", status="reviewed"),
        RagCitation(document_id="doc-b", chunk_id="c2", title="Doc B", source_path="s", file_name="f",
                     chunk_index=0, heading_path=None, snippet="s2", score=0.8,
                     retrieval_method="hybrid", status="reviewed"),
        RagCitation(document_id="doc-c", chunk_id="c3", title="Doc C", source_path="s", file_name="f",
                     chunk_index=0, heading_path=None, snippet="s3", score=0.7,
                     retrieval_method="hybrid", status="reviewed"),
    ]
    eq = compute_evidence_quality(citations)
    assert eq.citation_diversity == "high"
    assert eq.source_maturity == "strong"


def test_evidence_quality_draft_sources_weak_maturity():
    from semantic_lighthouse.schemas import RagCitation
    from semantic_lighthouse.services.chat import compute_evidence_quality

    citations = [
        RagCitation(document_id="doc-a", chunk_id="c1", title="T1", source_path="s", file_name="f",
                     chunk_index=0, heading_path=None, snippet="s1", score=0.9,
                     retrieval_method="hybrid", status="draft"),
        RagCitation(document_id="doc-b", chunk_id="c2", title="T2", source_path="s", file_name="f",
                     chunk_index=0, heading_path=None, snippet="s2", score=0.8,
                     retrieval_method="hybrid", status="draft"),
        RagCitation(document_id="doc-c", chunk_id="c3", title="T3", source_path="s", file_name="f",
                     chunk_index=0, heading_path=None, snippet="s3", score=0.7,
                     retrieval_method="hybrid", status="reviewed"),
    ]
    eq = compute_evidence_quality(citations)
    # 2/3 draft → >50% low maturity
    assert eq.source_maturity == "weak"


def test_citation_has_match_reason(client, tmp_path):
    """RAG answer response includes match_reason on each citation."""
    _, _, owner_headers = register_and_login(client, "owner@example.com")
    group_id = _create_group(client, owner_headers)
    _override_settings(client, _settings(tmp_path))
    _upload(
        client, group_id, owner_headers, "ontology.md",
        "# Ontology\n\nOntology connects business objects and AI workflows.",
    )

    response = client.post(
        f"/groups/{group_id}/rag/answer",
        json={"question": "Ontology 是什么？", "retrieval_method": "keyword"},
        headers=owner_headers,
    )
    assert response.status_code == 200
    payload = response.json()
    for citation in payload["citations"]:
        assert "match_reason" in citation
        assert len(citation["match_reason"]) > 0
        # should be Chinese
        assert any(ord(ch) > 127 for ch in citation["match_reason"])


def test_evidence_quality_in_response(client, tmp_path):
    """RAG answer response includes evidence_quality with valid summary."""
    _, _, owner_headers = register_and_login(client, "owner@example.com")
    group_id = _create_group(client, owner_headers)
    _override_settings(client, _settings(tmp_path))
    _upload(
        client, group_id, owner_headers, "ontology.md",
        "# Ontology\n\nOntology connects business objects and AI workflows.",
    )

    response = client.post(
        f"/groups/{group_id}/rag/answer",
        json={"question": "Ontology", "retrieval_method": "keyword"},
        headers=owner_headers,
    )
    assert response.status_code == 200
    payload = response.json()
    eq = payload.get("evidence_quality")
    assert eq is not None
    assert "retrieval_coverage" in eq
    assert "source_maturity" in eq
    assert "citation_diversity" in eq
    assert "score_distribution" in eq
    assert "summary" in eq
    assert len(eq["summary"]) > 0
    assert any(ord(ch) > 127 for ch in eq["summary"])


def test_match_reason_includes_keywords(client, tmp_path):
    """match_reason text should reference query keywords that were hit."""
    _, _, owner_headers = register_and_login(client, "owner@example.com")
    group_id = _create_group(client, owner_headers)
    _override_settings(client, _settings(tmp_path))
    _upload(
        client, group_id, owner_headers, "ontology.md",
        "# Ontology\n\nOntology connects data platforms and AI workflows.",
    )

    response = client.post(
        f"/groups/{group_id}/rag/answer",
        json={"question": "Ontology AI workflows", "retrieval_method": "keyword"},
        headers=owner_headers,
    )
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["citations"]) >= 1
    reason = payload["citations"][0]["match_reason"]
    # reason mentions at least one keyword from the query
    assert "Ontology" in reason or "AI" in reason or "workflows" in reason


def test_evidence_quality_no_evidence_response(client, tmp_path):
    """No-evidence path returns evidence_quality with coverage=none."""
    _, _, owner_headers = register_and_login(client, "owner@example.com")
    group_id = _create_group(client, owner_headers)
    _override_settings(client, _settings(tmp_path, chat_provider="deepseek"))
    _upload(client, group_id, owner_headers, "ontology.md", "# Ontology\n\nOntology content.")

    response = client.post(
        f"/groups/{group_id}/rag/answer",
        json={"question": "unmatched term xyz123", "retrieval_method": "keyword"},
        headers=owner_headers,
    )
    assert response.status_code == 200
    payload = response.json()
    eq = payload.get("evidence_quality")
    assert eq is not None
    assert eq["retrieval_coverage"] == "none"
    assert eq["citation_diversity"] == "none"
    assert payload["citations"] == []
