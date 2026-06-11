from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from conftest import register_and_login
from semantic_lighthouse.config import Settings, get_settings
from semantic_lighthouse.models import DocumentChunk


def _settings(path: Path, provider: str = "fake") -> Settings:
    return Settings(
        database_url="sqlite+pysqlite:///:memory:",
        jwt_secret_key="test-secret-key-at-least-32-bytes",
        cookie_secure=False,
        cookie_samesite="lax",
        knowledge_base_path=str(path),
        embedding_provider=provider,
        embedding_model="fake-embedding",
        embedding_dimension=8,
        embedding_batch_size=2,
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


def test_owner_can_rebuild_embeddings_and_member_cannot(client, db_session: Session, tmp_path):
    _, _, owner_headers = register_and_login(client, "owner@example.com")
    _, _, member_headers = register_and_login(client, "member@example.com")
    group_id = _create_group(client, owner_headers)
    _join_group(client, group_id, owner_headers, member_headers)
    _override_settings(client, _settings(tmp_path))
    _upload(client, group_id, owner_headers, "ontology.md", "# Ontology\n\nOntology connects business objects.")

    member_response = client.post(f"/groups/{group_id}/documents/embeddings/rebuild", headers=member_headers)
    owner_response = client.post(f"/groups/{group_id}/documents/embeddings/rebuild", headers=owner_headers)

    assert member_response.status_code == 403
    assert owner_response.status_code == 200
    assert owner_response.json()["processed_count"] == 1
    assert owner_response.json()["embedding_model"] == "fake-embedding"
    chunk = db_session.scalar(select(DocumentChunk).where(DocumentChunk.group_id == group_id))
    assert chunk.embedding is not None
    assert len(chunk.embedding) == 8
    assert chunk.embedding_model == "fake-embedding"
    assert chunk.embedded_at is not None


def test_rebuild_skips_existing_embeddings_unless_forced(client, tmp_path):
    _, _, owner_headers = register_and_login(client, "owner@example.com")
    group_id = _create_group(client, owner_headers)
    _override_settings(client, _settings(tmp_path))
    _upload(client, group_id, owner_headers, "ontology.md", "# Ontology\n\nOntology connects business objects.")

    first = client.post(f"/groups/{group_id}/documents/embeddings/rebuild", headers=owner_headers)
    second = client.post(f"/groups/{group_id}/documents/embeddings/rebuild", headers=owner_headers)
    forced = client.post(
        f"/groups/{group_id}/documents/embeddings/rebuild",
        params={"force": "true"},
        headers=owner_headers,
    )

    assert first.json()["processed_count"] == 1
    assert second.json()["processed_count"] == 0
    assert second.json()["skipped_count"] == 1
    assert forced.json()["processed_count"] == 1


def test_semantic_search_returns_citation_fields_and_score(client, tmp_path):
    _, _, owner_headers = register_and_login(client, "owner@example.com")
    _, _, member_headers = register_and_login(client, "member@example.com")
    group_id = _create_group(client, owner_headers)
    _join_group(client, group_id, owner_headers, member_headers)
    _override_settings(client, _settings(tmp_path))
    document_id = _upload(
        client,
        group_id,
        owner_headers,
        "roadmap.md",
        """---
title: AI Roadmap
entityType: Methodology
source: personal-analysis
status: draft
---

# AI Transformation

Ontology helps enterprise AI transformation.
""",
    )
    client.post(f"/groups/{group_id}/documents/embeddings/rebuild", headers=owner_headers)

    response = client.get(
        f"/groups/{group_id}/documents/semantic-search",
        params={"q": "enterprise ontology", "limit": 5},
        headers=member_headers,
    )

    assert response.status_code == 200
    result = response.json()[0]
    assert result["document_id"] == document_id
    assert result["chunk_id"]
    assert result["score"] <= 1.0
    assert result["retrieval_method"] == "semantic"
    assert result["title"] == "AI Roadmap"
    assert result["entity_type"] == "Methodology"
    assert result["source_path"] == "upload:roadmap.md"


def test_non_member_cannot_semantic_search(client, tmp_path):
    _, _, owner_headers = register_and_login(client, "owner@example.com")
    _, _, outsider_headers = register_and_login(client, "outsider@example.com")
    group_id = _create_group(client, owner_headers)
    _override_settings(client, _settings(tmp_path))

    response = client.get(
        f"/groups/{group_id}/documents/semantic-search",
        params={"q": "ontology"},
        headers=outsider_headers,
    )

    assert response.status_code == 403


def test_semantic_search_is_filtered_by_group_id(client, tmp_path):
    _, _, owner_headers = register_and_login(client, "owner@example.com")
    group_a = _create_group(client, owner_headers, "A")
    group_b = _create_group(client, owner_headers, "B")
    _override_settings(client, _settings(tmp_path))
    _upload(client, group_a, owner_headers, "a.md", "# A\n\nshared semantic content for group A")
    _upload(client, group_b, owner_headers, "b.md", "# B\n\nshared semantic content for group B")
    client.post(f"/groups/{group_a}/documents/embeddings/rebuild", headers=owner_headers)
    client.post(f"/groups/{group_b}/documents/embeddings/rebuild", headers=owner_headers)

    response = client.get(
        f"/groups/{group_a}/documents/semantic-search",
        params={"q": "shared semantic"},
        headers=owner_headers,
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["source_path"] == "upload:a.md"


def test_missing_aliyun_api_key_returns_clear_error(client, db_session: Session, tmp_path):
    _, _, owner_headers = register_and_login(client, "owner@example.com")
    group_id = _create_group(client, owner_headers)
    _override_settings(client, _settings(tmp_path, provider="aliyun"))
    _upload(client, group_id, owner_headers, "ontology.md", "# Ontology\n\ncontent")

    response = client.post(f"/groups/{group_id}/documents/embeddings/rebuild", headers=owner_headers)

    assert response.status_code == 502
    assert "DASHSCOPE_API_KEY" in response.json()["detail"]
    chunk = db_session.scalar(select(DocumentChunk).where(DocumentChunk.group_id == group_id))
    assert chunk.embedding is None
