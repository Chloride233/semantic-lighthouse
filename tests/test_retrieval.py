"""Tests for Phase 1 retrieval: hybrid search, scoring, dedup, isolation."""

from types import SimpleNamespace

from conftest import register_and_login
from semantic_lighthouse.config import Settings, get_settings


def _create_group(client, headers, name="Eval"):
    r = client.post("/groups", json={"name": name}, headers=headers)
    assert r.status_code == 201
    return r.json()["id"]


def _override_settings(client, tmp_path):
    def override():
        return Settings(
            database_url="sqlite+pysqlite:///:memory:",
            jwt_secret_key="test-secret-key-at-least-32-bytes",
            cookie_secure=False, cookie_samesite="lax",
            document_storage_path=str(tmp_path / "doc-store"),
            upload_tmp_path=str(tmp_path / "upload-tmp"),
            embedding_provider="fake",
            chat_provider="fake",
            upload_chunk_bytes=8,
        )
    client.app.dependency_overrides[get_settings] = override


def _upload_md(client, group_id, headers, title, body):
    content = f"# {title}\n\n{body}".encode()
    return client.post(
        f"/groups/{group_id}/documents/upload",
        files={"file": (f"{title}.md", content, "text/markdown")},
        headers=headers,
    )


def test_hybrid_endpoint_returns_scored_results(client, tmp_path):
    _, _, h = register_and_login(client, "o@t.com")
    gid = _create_group(client, h)
    _override_settings(client, tmp_path)
    _upload_md(client, gid, h, "Alpha", "hybrid search test content alpha")
    _upload_md(client, gid, h, "Beta", "hybrid test beta content")

    r = client.get(f"/groups/{gid}/documents/search/hybrid", params={"q": "hybrid search"}, headers=h)
    assert r.status_code == 200
    results = r.json()
    assert len(results) >= 1
    for item in results:
        assert item["retrieval_method"] == "hybrid"
        assert "score" in item
        assert item["score"] >= 0.0


def test_hybrid_discards_zero_score_semantic_noise(monkeypatch):
    from semantic_lighthouse.services import retrieval

    chunk = SimpleNamespace(id="fixed-noise")
    document = SimpleNamespace()
    monkeypatch.setattr(retrieval, "_keyword_search", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        retrieval,
        "_semantic_search",
        lambda *args, **kwargs: [
            retrieval.ScoredChunk(
                chunk=chunk,
                document=document,
                score=0.0,
                retrieval_method="semantic",
            )
        ],
    )

    results = retrieval.hybrid_search(
        db=SimpleNamespace(),
        group_id="g1",
        query="任意问题",
        limit=5,
        keyword_weight=0.3,
        settings=Settings(),
    )

    assert results == []


def test_hybrid_keyword_uses_terms_not_full_question(client, tmp_path):
    _, _, h = register_and_login(client, "terms@t.com")
    gid = _create_group(client, h)
    _override_settings(client, tmp_path)
    _upload_md(client, gid, h, "Ontology", "Ontology connects business semantics and data platforms.")
    _upload_md(client, gid, h, "Unrelated", "Unrelated document about coffee beans.")

    response = client.get(
        f"/groups/{gid}/documents/search/hybrid",
        params={"q": "企业为什么需要 Ontology？", "keyword_weight": 1.0},
        headers=h,
    )

    assert response.status_code == 200
    results = response.json()
    assert results
    assert results[0]["title"] == "Ontology"


def test_hybrid_respects_group_isolation(client, tmp_path):
    _, _, ha = register_and_login(client, "a@t.com")
    _, _, hb = register_and_login(client, "b@t.com")
    ga = _create_group(client, ha, "A")
    gb = _create_group(client, hb, "B")
    _override_settings(client, tmp_path)
    _upload_md(client, ga, ha, "Alpha", "unique keyword xyz")

    r = client.get(f"/groups/{gb}/documents/search/hybrid", params={"q": "xyz"}, headers=hb)
    assert r.status_code == 200
    assert len(r.json()) == 0


def test_hybrid_dedup_same_chunk_appears_once(client, tmp_path):
    _, _, h = register_and_login(client, "o@t.com")
    gid = _create_group(client, h)
    _override_settings(client, tmp_path)
    _upload_md(client, gid, h, "Dedup", "dedup test content keyword match")

    r = client.get(f"/groups/{gid}/documents/search/hybrid", params={"q": "dedup"}, headers=h)
    assert r.status_code == 200
    ids = [item["chunk_id"] for item in r.json()]
    assert len(ids) == len(set(ids)), "Duplicate chunk_ids in hybrid results"


def test_hybrid_keyword_weight_zero_semantic_only(client, tmp_path):
    _, _, h = register_and_login(client, "o@t.com")
    gid = _create_group(client, h)
    _override_settings(client, tmp_path)
    _upload_md(client, gid, h, "Sem", "semantic weight test")

    r = client.get(f"/groups/{gid}/documents/search/hybrid", params={"q": "weight", "keyword_weight": 0.0}, headers=h)
    assert r.status_code == 200


def test_hybrid_semantic_only_ignores_chunks_without_embeddings(client, tmp_path):
    _, _, h = register_and_login(client, "noembed@t.com")
    gid = _create_group(client, h)
    _override_settings(client, tmp_path)
    _upload_md(client, gid, h, "NoEmbedding", "This document has not rebuilt embeddings yet.")

    response = client.get(
        f"/groups/{gid}/documents/search/hybrid",
        params={"q": "anything", "keyword_weight": 0.0},
        headers=h,
    )

    assert response.status_code == 200
    assert response.json() == []


def test_hybrid_keyword_weight_one_keyword_only(client, tmp_path):
    _, _, h = register_and_login(client, "o@t.com")
    gid = _create_group(client, h)
    _override_settings(client, tmp_path)
    _upload_md(client, gid, h, "KW", "keyword weight test")

    r = client.get(f"/groups/{gid}/documents/search/hybrid", params={"q": "keyword weight", "keyword_weight": 1.0}, headers=h)
    assert r.status_code == 200


def test_hybrid_excludes_non_ready_documents(client, db_session, tmp_path):
    _, _, h = register_and_login(client, "o@t.com")
    gid = _create_group(client, h)
    _override_settings(client, tmp_path)

    from semantic_lighthouse.models import Document as Doc
    from semantic_lighthouse.services.document_ingestion import hash_text

    doc = Doc(
        group_id=gid, title="Draft", file_name="draft.md",
        source_path="upload:draft.md", content_hash=hash_text("# Draft\ndraft"),
        raw_content="# Draft\ndraft content", status="uploaded", created_by="t",
    )
    db_session.add(doc)
    db_session.commit()

    r = client.get(f"/groups/{gid}/documents/search/hybrid", params={"q": "draft"}, headers=h)
    assert r.status_code == 200
    assert len(r.json()) == 0


def test_rag_defaults_to_hybrid(client, tmp_path):
    _, _, h = register_and_login(client, "o@t.com")
    gid = _create_group(client, h)
    _override_settings(client, tmp_path)
    _upload_md(client, gid, h, "RAG", "RAG retrieval method test document content")

    r = client.post(f"/groups/{gid}/rag/answer", json={"question": "retrieval test"}, headers=h)
    assert r.status_code == 200
    assert r.json()["retrieval_method"] == "hybrid"


def test_rag_forced_keyword_still_works(client, tmp_path):
    _, _, h = register_and_login(client, "o@t.com")
    gid = _create_group(client, h)
    _override_settings(client, tmp_path)
    _upload_md(client, gid, h, "KW2", "forced keyword test")

    r = client.post(
        f"/groups/{gid}/rag/answer",
        json={"question": "keyword", "retrieval_method": "keyword"},
        headers=h,
    )
    assert r.status_code == 200
    assert r.json()["retrieval_method"] == "keyword"
