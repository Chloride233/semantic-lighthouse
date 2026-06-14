<!-- Generated: 2026-06-12 | Files: 24 | ~700 tokens -->

# Backend API

## Routes

| Method | Path | Router | Auth |
|--------|------|--------|------|
| `POST` | `/auth/register` | auth.py | None |
| `POST` | `/auth/login` | auth.py | None |
| `POST` | `/auth/refresh` | auth.py | Cookie |
| `POST` | `/auth/logout` | auth.py | Cookie |
| `GET` | `/auth/me` | auth.py | Bearer |
| `POST` | `/groups` | groups.py | Bearer |
| `GET` | `/groups` | groups.py | Bearer |
| `GET/POST` | `/groups/{id}/invites` | groups.py | Bearer + role |
| `POST` | `/groups/join-by-invite` | groups.py | Bearer |
| `POST` | `/groups/{id}/join-requests` | groups.py | Bearer |
| `PATCH` | `/groups/{id}/members/{uid}` | groups.py | Owner/Admin |
| `POST` | `/groups/{gid}/documents/import-local` | documents.py | Bearer |
| `POST` | `/groups/{gid}/documents/upload` | documents.py | Bearer |
| `POST` | `/groups/{gid}/documents/uploads/init` | documents.py | Bearer |
| `PUT` | `.../uploads/{uid}/chunks/{idx}` | documents.py | Bearer |
| `GET` | `.../uploads/{uid}` | documents.py | Owner/Admin |
| `POST` | `.../uploads/{uid}/complete` | documents.py | Bearer |
| `GET` | `/groups/{gid}/documents/search` | documents.py | Bearer |
| `GET` | `.../documents/semantic-search` | documents.py | Bearer |
| `POST` | `.../documents/embeddings/rebuild` | documents.py | Owner/Admin |
| `POST` | `.../documents/{did}/archive` | documents.py | Owner/Admin |
| `POST` | `.../documents/{did}/unarchive` | documents.py | Owner/Admin |
| `POST` | `.../documents/{did}/ingestion-jobs` | documents.py | Owner/Admin |
| `GET` | `.../documents/{did}/ingestion-jobs` | documents.py | Bearer |
| `GET` | `.../documents/ingestion-jobs/{jid}` | documents.py | Bearer |
| `POST` | `/groups/{gid}/rag/answer` | rag.py | Bearer |
| `GET` | `/groups/{gid}/rag/runs` | rag.py | Bearer |
| `GET` | `/groups/{gid}/rag/runs/{rid}` | rag.py | Bearer |
| `POST` | `/groups/{gid}/conversations` | conversations.py | Bearer |
| `GET` | `/groups/{gid}/conversations` | conversations.py | Bearer |
| `GET` | `/groups/{gid}/conversations/{cid}` | conversations.py | Bearer + owner |
| `POST` | `.../conversations/{cid}/messages` | conversations.py | Bearer + owner |
| `POST` | `/groups/{gid}/agent/runs` | agent.py | Bearer |
| `GET` | `/groups/{gid}/agent/runs` | agent.py | Bearer |
| `GET` | `/groups/{gid}/agent/runs/{rid}` | agent.py | Bearer + owner |
| `POST` | `/groups/{gid}/agent/runs/{rid}/execute` | agent.py | Bearer + owner |
| `GET` | `/groups/{gid}/agent/runs/{rid}/steps` | agent.py | Bearer + owner |
| `POST` | `/groups/{gid}/agent/runs/{rid}/respond` | agent.py | Bearer + owner |
| `GET` | `/groups/{gid}/agent/memories` | agent.py | Bearer |
| `POST` | `/groups/{gid}/agent/memories` | agent.py | Bearer |
| `DELETE` | `/groups/{gid}/agent/memories/{mid}` | agent.py | Bearer |
| `GET` | `/health` | main.py | None |
| `GET` | `/console` | main.py | None |
| `GET` | `/static/*` | StaticFiles | None |

## Services

| Service | Lines | Key Functions |
|---------|-------|---------------|
| `chat.py` | 360 | `create_chat_client()`, `sanitize_references()`, `adjusted_confidence()`, `ChatClient.answer_question()`, `ChatClient.generate_response()` |
| `document_etl.py` | 471 | `run_etl_job()` (7-step pipeline), `chunk_structured()`, `_extract_markdown()` |
| `document_ingestion.py` | 201 | `ingest_markdown()`, `chunk_markdown()` |
| `document_uploads.py` | 199 | `init_upload()`, `save_chunk()`, `complete_upload()` |
| `document_files.py` | 118 | `verify_file_hash()` (streaming SHA-256), `parse_document()` |
| `retrieval.py` | 212 | `hybrid_search()`, `_keyword_search()`, `_semantic_search_with_vector()`, `ScoredChunk` |
| `embeddings.py` | 103 | `create_embedding_client()`, `FakeEmbeddingClient`, `AliyunEmbeddingClient` |
| `agent_orchestrator.py` | 236 | `ToolDef`, `AGENT_TOOLS`, `execute_tool()`, `create_run()`, `add_step()`, `finalize_run()`, `fail_run()`, `upsert_memory()` |

## Auth Flow

```
register → bcrypt hash → users table
login → JWT access (15m) + refresh cookie (httpOnly, DB-stored hash)
refresh → rotate token family, invalidate old, detect replay
logout → revoke token family in DB
every request → Bearer extraction → JWT decode → user lookup → get_membership_or_404
```

## Ingestion Pipeline (async ETL)

```
upload complete → status=uploaded → BackgroundTasks.run_etl_job()
  ┌─ Extract (file→text via parser)
  ├─ Parse (frontmatter)
  ├─ Clean (normalize whitespace)
  ├─ Chunk (structure-aware: headings→paragraphs→sentences→split)
  ├─ Embedding (batch API call, retry×3 with backoff)
  ├─ Load (insert chunks + embeddings)
  └─ Finalize (status=ready, processed_at)
```

## Retrieval Methods

| Method | Implementation | Uses |
|--------|---------------|------|
| `keyword` | ILIKE across chunk content + document title + source_path | No embeddings needed |
| `semantic` | pgvector cosine distance (HNSW index) | Embedding API required |
| `hybrid` | Linear score fusion: `kw_weight * norm_kw + (1-kw) * norm_sem` | Both |
| `auto` | Semantic first, fall back to keyword | Embedding optional |
