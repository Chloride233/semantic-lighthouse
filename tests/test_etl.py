"""Tests for V3.4 document ETL ingestion pipeline.

Each test has exactly one expected outcome — no ``in (...)`` ambiguity.
"""

from hashlib import sha256
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from conftest import register_and_login
from semantic_lighthouse.config import Settings, get_settings
from semantic_lighthouse.models import IngestionJob


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


def _override_etl_settings(client: TestClient, tmp_path: Path, **extra) -> None:
    kwargs = dict(
        database_url="sqlite+pysqlite:///:memory:",
        jwt_secret_key="test-secret-key-at-least-32-bytes",
        cookie_secure=False,
        cookie_samesite="lax",
        document_storage_path=str(tmp_path / "document-storage"),
        upload_tmp_path=str(tmp_path / "upload-tmp"),
        max_document_upload_bytes=50 * 1024 * 1024,
        embedding_provider="fake",
        upload_chunk_bytes=8,
    )
    kwargs.update(extra)

    def override() -> Settings:
        return Settings(**kwargs)

    client.app.dependency_overrides[get_settings] = override


def _chunked_upload_complete(client, group_id, headers, content, chunk_size=8):
    """Helper: init → chunk(s) → complete, return response."""
    file_hash = sha256(content).hexdigest()
    init = client.post(
        f"/groups/{group_id}/documents/uploads/init",
        json={"file_name": "test.md", "file_size": len(content), "file_hash": file_hash, "chunk_size": chunk_size},
        headers=headers,
    )
    upload_id = init.json()["upload_id"]
    for start in range(0, len(content), chunk_size):
        end = min(start + chunk_size, len(content))
        client.put(
            f"/groups/{group_id}/documents/uploads/{upload_id}/chunks/{start // chunk_size}",
            files={"file": (f"{start // chunk_size}.part", content[start:end], "application/octet-stream")},
            headers=headers,
        )
    return client.post(f"/groups/{group_id}/documents/uploads/{upload_id}/complete", headers=headers)


# ── happy-path tests ──────────────────────────────────────────────────────


def test_etl_sets_document_ready_and_produces_chunks_with_embeddings(client, tmp_path):
    """Complete → ETL → document ready, chunks with embeddings, searchable."""
    _, _, owner_headers = register_and_login(client, "owner@example.com")
    group_id = _create_group(client, owner_headers)
    _override_etl_settings(client, tmp_path)
    content = b"# ETL Test\n\nThis document goes through the ETL pipeline."

    complete = _chunked_upload_complete(client, group_id, owner_headers, content)
    assert complete.status_code == 200
    doc_id = complete.json()["id"]

    # ETL runs via BackgroundTasks after response — re-fetch to get final status.
    detail = client.get(f"/groups/{group_id}/documents/{doc_id}", headers=owner_headers)
    assert detail.status_code == 200
    doc = detail.json()
    assert doc["status"] == "ready", f"Expected ready after ETL, got {doc['status']}"
    assert doc["title"] == "ETL Test"

    chunks = doc["chunks"]
    assert len(chunks) >= 1
    for chunk in chunks:
        assert "content" in chunk
        assert "content_hash" in chunk

    # Keyword search must find it
    search = client.get(f"/groups/{group_id}/documents/search", params={"q": "ETL pipeline"}, headers=owner_headers)
    assert search.status_code == 200
    assert any(r["document_id"] == doc_id for r in search.json())


def test_etl_ingestion_job_succeeded_with_step_log(client, db_session: Session, tmp_path):
    """After ETL, job is succeeded and step_log is persisted through DB reload."""
    _, _, owner_headers = register_and_login(client, "owner@example.com")
    group_id = _create_group(client, owner_headers)
    _override_etl_settings(client, tmp_path)
    content = b"# Step Log\n\nverify step_log persistence"

    complete = _chunked_upload_complete(client, group_id, owner_headers, content)
    doc_id = complete.json()["id"]

    jobs = client.get(f"/groups/{group_id}/documents/{doc_id}/ingestion-jobs", headers=owner_headers)
    job = jobs.json()[0]
    assert job["status"] == "succeeded"
    assert job["document_id"] == doc_id

    # Reload from DB to verify step_log is really persisted
    from sqlalchemy import select
    db_job = db_session.scalar(select(IngestionJob).where(IngestionJob.id == job["id"]))
    assert db_job is not None
    log = db_job.step_log
    expected_steps = {"extract", "parse", "clean", "chunk", "embed", "load", "finalized_at"}
    missing = expected_steps - set(log.keys())
    assert not missing, f"step_log missing keys after DB reload: {missing}"


# ── retry-and-failure tests ───────────────────────────────────────────────


def test_etl_retries_then_succeeds(client, tmp_path, monkeypatch):
    """Embedding fails twice, succeeds on third attempt — attempt_count=3, doc ready."""
    _, _, owner_headers = register_and_login(client, "owner@example.com")
    group_id = _create_group(client, owner_headers)
    _override_etl_settings(client, tmp_path, embedding_provider="fake")

    from semantic_lighthouse.services import embeddings as emb_module

    call_count = [0]
    original_embed = emb_module.FakeEmbeddingClient.embed_texts

    def flaky_embed(self, texts):
        call_count[0] += 1
        if call_count[0] < 3:
            raise emb_module.EmbeddingError(f"Simulated failure #{call_count[0]}")
        return original_embed(self, texts)

    monkeypatch.setattr(emb_module.FakeEmbeddingClient, "embed_texts", flaky_embed)

    content = b"# Retry\n\nretry succeeds on third attempt"
    complete = _chunked_upload_complete(client, group_id, owner_headers, content)
    doc_id = complete.json()["id"]

    doc = client.get(f"/groups/{group_id}/documents/{doc_id}", headers=owner_headers).json()
    assert doc["status"] == "ready", f"Expected ready after ETL, got {doc['status']}"
    assert call_count[0] == 3, f"Expected 3 attempts, got {call_count[0]}"

    jobs = client.get(f"/groups/{group_id}/documents/{doc['id']}/ingestion-jobs", headers=owner_headers)
    job = jobs.json()[0]
    assert job["status"] == "succeeded"
    assert job["attempt_count"] == 3


def test_ready_document_survives_failed_retry(client, tmp_path, monkeypatch):
    """Manual retry on a ready doc that fails — doc stays ready, old chunks searchable."""
    _, _, owner_headers = register_and_login(client, "owner@example.com")
    group_id = _create_group(client, owner_headers)
    _override_etl_settings(client, tmp_path, embedding_provider="fake")

    # First upload: succeeds
    content = b"# Survive\n\nthis document survives a failed retry"
    complete = _chunked_upload_complete(client, group_id, owner_headers, content)
    doc_id = complete.json()["id"]

    doc = client.get(f"/groups/{group_id}/documents/{doc_id}", headers=owner_headers).json()
    assert doc["status"] == "ready", f"Expected ready after first ETL, got {doc['status']}"

    # Verify keyword search works
    search_before = client.get(f"/groups/{group_id}/documents/search", params={"q": "survives"}, headers=owner_headers)
    assert search_before.status_code == 200
    assert any(r["document_id"] == doc_id for r in search_before.json())

    # Now make the embedding provider always fail
    from semantic_lighthouse.services import embeddings as emb_module

    def always_fail(self, texts):
        raise emb_module.EmbeddingError("Simulated permanent failure")

    monkeypatch.setattr(emb_module.FakeEmbeddingClient, "embed_texts", always_fail)

    # Manual retry — should fail
    retry = client.post(f"/groups/{group_id}/documents/{doc_id}/ingestion-jobs", headers=owner_headers)
    assert retry.status_code == 201
    retry_job = retry.json()

    # Job should have failed
    job_detail = client.get(
        f"/groups/{group_id}/documents/ingestion-jobs/{retry_job['id']}", headers=owner_headers
    )
    assert job_detail.json()["status"] == "failed"
    assert "Simulated permanent failure" in job_detail.json()["error_message"]

    # Document must still be ready
    doc_after = client.get(f"/groups/{group_id}/documents/{doc_id}", headers=owner_headers)
    assert doc_after.json()["status"] == "ready"

    # Keyword search must still find it
    search_after = client.get(f"/groups/{group_id}/documents/search", params={"q": "survives"}, headers=owner_headers)
    assert search_after.status_code == 200
    assert any(r["document_id"] == doc_id for r in search_after.json()), "Ready doc must remain searchable after failed retry"


# ── permission tests ──────────────────────────────────────────────────────


def test_member_cannot_create_ingestion_job(client, tmp_path):
    """Member POST to ingestion-jobs returns 403."""
    _, _, owner_headers = register_and_login(client, "owner@example.com")
    _, _, member_headers = register_and_login(client, "member@example.com")
    group_id = _create_group(client, owner_headers)
    _join_group(client, group_id, owner_headers, member_headers)
    _override_etl_settings(client, tmp_path)
    content = b"# Member\n\nno permission"

    complete = _chunked_upload_complete(client, group_id, owner_headers, content)
    doc_id = complete.json()["id"]

    response = client.post(f"/groups/{group_id}/documents/{doc_id}/ingestion-jobs", headers=member_headers)
    assert response.status_code == 403


def test_member_can_view_ingestion_jobs(client, tmp_path):
    """Member can GET ingestion jobs for a document in their group."""
    _, _, owner_headers = register_and_login(client, "owner@example.com")
    _, _, member_headers = register_and_login(client, "member@example.com")
    group_id = _create_group(client, owner_headers)
    _join_group(client, group_id, owner_headers, member_headers)
    _override_etl_settings(client, tmp_path)
    content = b"# View\n\nmember view test"

    complete = _chunked_upload_complete(client, group_id, owner_headers, content)
    doc_id = complete.json()["id"]

    jobs = client.get(f"/groups/{group_id}/documents/{doc_id}/ingestion-jobs", headers=member_headers)
    assert jobs.status_code == 200


def test_non_member_cannot_view_ingestion_jobs(client, tmp_path):
    """Non-member GET ingestion jobs returns 403."""
    _, _, owner_headers = register_and_login(client, "owner@example.com")
    _, _, outsider_headers = register_and_login(client, "outsider@example.com")
    group_id = _create_group(client, owner_headers)
    _override_etl_settings(client, tmp_path)
    content = b"# Outsider\n\nno access"

    complete = _chunked_upload_complete(client, group_id, owner_headers, content)
    doc_id = complete.json()["id"]

    jobs = client.get(f"/groups/{group_id}/documents/{doc_id}/ingestion-jobs", headers=outsider_headers)
    assert jobs.status_code == 403


def test_cross_group_ingestion_job_isolation(client, tmp_path):
    """Group A owner cannot see group B's ingestion jobs."""
    _, _, owner_a_headers = register_and_login(client, "owner-a@example.com")
    _, _, owner_b_headers = register_and_login(client, "owner-b@example.com")
    group_a = _create_group(client, owner_a_headers, "A")
    _create_group(client, owner_b_headers, "B")  # group_b — only needed to exist
    _override_etl_settings(client, tmp_path)
    content = b"# Isolation\n\ncross group test"

    complete = _chunked_upload_complete(client, group_a, owner_a_headers, content)
    doc_id = complete.json()["id"]

    jobs = client.get(f"/groups/{group_a}/documents/{doc_id}/ingestion-jobs", headers=owner_b_headers)
    assert jobs.status_code == 403


def test_search_excludes_non_ready_documents(client, db_session: Session, tmp_path):
    """Keyword search does not return documents with status=uploaded."""
    _, _, owner_headers = register_and_login(client, "owner@example.com")
    group_id = _create_group(client, owner_headers)
    _override_etl_settings(client, tmp_path)

    from semantic_lighthouse.models import Document as DocModel
    from semantic_lighthouse.services.document_ingestion import hash_text

    content_text = "# Draft\n\ndraft content unique-keyword-xyz"
    doc = DocModel(
        group_id=group_id,
        title="Draft",
        file_name="draft.md",
        source_path="upload:draft.md",
        content_hash=hash_text(content_text),
        raw_content=content_text,
        status="uploaded",
        created_by="test",
    )
    db_session.add(doc)
    db_session.commit()

    search = client.get(
        f"/groups/{group_id}/documents/search",
        params={"q": "unique-keyword-xyz"},
        headers=owner_headers,
    )
    assert search.status_code == 200
    assert len(search.json()) == 0, "Uploaded (not ready) documents should not appear in search"
