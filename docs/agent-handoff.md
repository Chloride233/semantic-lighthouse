# Agent Handoff Snapshot

Last updated: 2026-06-12 03:00:00 +08:00

## Current Phase

**Phase 0: Engineering Baseline Stabilization** — see `docs/project-roadmap.md` for the full 6-phase plan.

Next priority tasks (Phase 0):
1. V3.4 ETL final verification (pytest + ruff + Alembic)
2. PostgreSQL + pgvector real smoke (local Docker or cloud ECS)
3. .gitignore audit for secrets, artifacts, runtime data
4. Cloud smoke playbook review

## Git Repository

- **Initialized**: 2026-06-12
- **Initial commit**: `87c33cc` — `chore: initialize semantic lighthouse repository`
- **Branch**: `master`
- **Remote**: not configured (local-only)
- **.gitignore**: excludes `.venv/`, `.env*` (keeps `.example`), `*.db`, `.tmp/`, `.claude/`, build artifacts, storage volumes

This file is the short-term operating memory for any coding agent taking over Semantic Lighthouse. It should be updated at the end of every meaningful iteration.

## Current Project State

Semantic Lighthouse is currently a FastAPI backend with PostgreSQL, SQLAlchemy, Alembic, pgvector support, and cloud-provider abstractions for embedding and chat.

Completed capabilities:

- V1: user registration, login, logout, BCrypt password hashing, short-lived JWT access token, httpOnly refresh cookie, refresh token rotation, replay detection, group roles, and `group_id` authorization.
- V2: Markdown document ingestion, local knowledge-base import, single-file upload, document chunks, keyword search, and citation-ready metadata.
- V2.1: Aliyun Model Studio / DashScope embedding provider, fake test provider, pgvector-ready chunk embeddings, manual embedding rebuild, and semantic search.
- V2.2: MD/TXT/PDF/DOCX ingestion, three-stage chunked upload, group-scoped instant upload, resumable sessions, idempotent chunks, local upload temp storage, and original-file metadata.
- V3: DeepSeek/OpenAI-compatible chat provider, citation-grounded RAG answer endpoint, confidence, knowledge gaps, next steps, and local evidence gate.
- V3.3: persisted RAG run audit records with group-scoped run listing and detail lookup.
- V3.4: DB-backed async ETL ingestion pipeline with structure-aware chunking; HNSW index on chunks; ingestion job tracking; startup crash recovery.

Current important API surfaces:

- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/refresh`
- `POST /auth/logout`
- `GET /auth/me`
- `POST /groups`
- group invite, join request, approval, and role-management endpoints
- `POST /groups/{group_id}/documents/import-local`
- `POST /groups/{group_id}/documents/upload`
- `POST /groups/{group_id}/documents/uploads/init`
- `PUT /groups/{group_id}/documents/uploads/{upload_id}/chunks/{chunk_index}`
- `GET /groups/{group_id}/documents/uploads/{upload_id}`
- `POST /groups/{group_id}/documents/uploads/{upload_id}/complete`
- `GET /groups/{group_id}/documents/search`
- `POST /groups/{group_id}/documents/embeddings/rebuild`
- `GET /groups/{group_id}/documents/semantic-search`
- `POST /groups/{group_id}/rag/answer`
- `GET /groups/{group_id}/rag/runs`
- `GET /groups/{group_id}/rag/runs/{run_id}`
- `POST /groups/{group_id}/documents/{document_id}/ingestion-jobs`
- `GET /groups/{group_id}/documents/{document_id}/ingestion-jobs`
- `GET /groups/{group_id}/documents/ingestion-jobs/{job_id}`

## Verification Status

Most recent known local review before this handoff:

- Full test suite: **54 passed, 111 warnings** (was 46; +8 new ETL pipeline tests).
- Alembic migration from empty SQLite database reached `0006_v34_ingestion_jobs`.
- The FastAPI / Docker cloud deployment had previously run on Alibaba Cloud ECS up through the V3 cloud chain.

Latest local verification:

```text
2026-06-12 02:00:00 +08:00

Command:
.\.venv\Scripts\python -m pytest -p no:cacheprovider --basetemp=.tmp/pytest-temp

Result:
55 passed, 1 warning

Warning:
StarletteDeprecationWarning only (FastAPI on_event→lifespan migration completed).

Command:
.\.venv\Scripts\ruff check src tests

Result:
All checks passed!

Command:
.\.venv\Scripts\python -m alembic upgrade head
.\.venv\Scripts\python -m alembic current

Result:
0006_v34_ingestion_jobs (head)
```

## Current Risks And Next Priority

V3.4 ETL pipeline **delivered and hardened in this iteration**:
- DB-backed `ingestion_jobs` table with status state machine.
- FastAPI `BackgroundTasks` async ETL (Extract→Parse→Clean→Chunk→Embedding→Load).
- Structure-aware chunking with configurable min/max/target character limits.
- HNSW index on `document_chunks.embedding` (PostgreSQL-only, `m=16, ef_construction=200`).
- Startup recovery for orphaned jobs and documents (lifespan-based).
- 3 ingestion job API endpoints with group-scoped permissions.
- RAG/search now filters by `Document.status == "ready"`.

**V3.4 hardening fixes (P1/P2 round)**:
- P1-1: `PGVECTOR_DIMENSION` NameError fixed — imported from `_shared.py`.
- P1-2: `EmbeddingError` now flows through the 3-attempt retry loop instead of bypassing it.
- P1-3: Manual retry on ready documents no longer breaks existing chunks; ready doc survives failed retry.
- P2-1: `step_log` uses `MutableDict.as_mutable(JSON)` + explicit dict assignment for reliable persistence.
- P2-2: Test assertions tightened — no `in (...)` ambiguity; explicit success/failure path tests.
- P2-3: ETL scope documented — chunked upload complete only; import-local and `/upload` remain synchronous.
- Test suite now uses file-backed SQLite to support BackgroundTasks across threads.
- Ruff lint: zero errors.

**ETL scope boundary** (P2-3):
- `POST /uploads/{id}/complete` → async ETL pipeline with ingestion_jobs.
- `POST /upload` (single file) and `POST /import-local` → synchronous `ingest_markdown`, no ingestion_jobs.
- This is intentional: the ETL pipeline targets multi-format chunked uploads; small Markdown stays fast.

Known remaining risks:

- ✅ Upload chunk temp files are now cleaned after successful `complete` (`cleanup_upload_temp_dir`).
- ✅ Hash mismatch now cleans both the merged file and temp chunks before raising.
- ✅ Parser failure now cleans both the merged file and temp chunks before raising.
- ✅ `complete` uses streaming `verify_file_hash()` instead of `read_bytes()` for hash check — hash mismatch is caught without loading the full file into RAM.
- ✅ `GET /uploads/{upload_id}` now requires Owner/Admin (was any Member).
- ✅ Tests added for cleanup after success, cleanup after hash mismatch, cleanup after parser failure, and member GET rejection.

Known remaining risks:

- PDF parsing only handles extractable text and does not do OCR.
- DOCX parsing currently reads ordinary paragraphs and does not read tables, headers, or footers.
- Production compose depends on a real `.env.production`; local config checks fail if it is missing.
- `read_bytes()` is still used for the final parse step (after hash verification passes); acceptable for current 50 MiB limit but worth monitoring on a 2 GiB ECS.
- No max concurrent upload session limit per user/group.

Recommended next iteration:

1. Add DOCX table/header/footer extraction to improve retrieval quality.
2. Add a per-user concurrent upload session cap.
3. Consider replacing the post-hash `read_bytes()` with a streaming parse path.
4. Rerun full tests and migration smoke.
5. Update this handoff and engineering memory.

## Cloud Deployment Memory

Known server path:

```bash
/opt/semantic-lighthouse
```

Production compose command:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build
```

Status commands:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml ps
docker logs semantic-lighthouse-api --tail 100
curl -fsS http://127.0.0.1:8000/health
```

Cloud smoke playbook:

```text
docs/cloud-smoke-playbook.md
```

Do not store real `DASHSCOPE_API_KEY`, `DEEPSEEK_API_KEY`, database passwords, cookies, or tokens in this file.

## Agent Instructions For The Next Session

Start by reading `CLAUDE.md`, this handoff, and the latest engineering memory files. Then run review and tests before changing code.

The V2.2 upload cleanup iteration is complete. The next priority is either DOCX parsing improvements (tables/headers/footers) or moving to V4 Agent dialogue — whichever the project owner chooses. Do not jump to V4 without confirming the upload and RAG foundations stay verifiably usable.
