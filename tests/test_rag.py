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
    assert runs.status_code == 200
    assert runs.json()[0]["id"] == run_id
    assert runs.json()[0]["citation_count"] == 1
    assert detail.status_code == 200
    assert detail.json()["id"] == run_id
    assert detail.json()["question"] == "Ontology"
    assert detail.json()["citations"][0]["title"] == "Ontology"


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
    assert adjusted_confidence("high", citations) == "medium"


def test_adjusted_confidence_low_for_weak_scores():
    from semantic_lighthouse.schemas import RagCitation
    from semantic_lighthouse.services.chat import adjusted_confidence

    citations = [
        RagCitation(document_id="a", chunk_id="c1", title="T1", source_path="s", file_name="f",
                     chunk_index=0, heading_path=None, snippet="s1", score=0.1, retrieval_method="hybrid"),
        RagCitation(document_id="a", chunk_id="c2", title="T2", source_path="s", file_name="f",
                     chunk_index=1, heading_path=None, snippet="s2", score=0.2, retrieval_method="hybrid"),
    ]
    assert adjusted_confidence("high", citations) == "low"


def test_adjusted_confidence_preserves_high_for_strong_scores():
    from semantic_lighthouse.schemas import RagCitation
    from semantic_lighthouse.services.chat import adjusted_confidence

    citations = [
        RagCitation(document_id="a", chunk_id="c1", title="T1", source_path="s", file_name="f",
                     chunk_index=0, heading_path=None, snippet="s1", score=0.9, retrieval_method="hybrid"),
        RagCitation(document_id="a", chunk_id="c2", title="T2", source_path="s", file_name="f",
                     chunk_index=1, heading_path=None, snippet="s2", score=0.8, retrieval_method="hybrid"),
    ]
    assert adjusted_confidence("high", citations) == "high"
