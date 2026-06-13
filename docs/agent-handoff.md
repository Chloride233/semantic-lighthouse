# Agent Handoff Snapshot

Last updated: 2026-06-13

## Current Phase

**Phases 0–7 delivered** — see `docs/project-roadmap.md`.

- **Phase 1**: Hybrid search + retrieval eval
- **Phase 2**: Archive/unarchive + document lifecycle
- **Phase 3**: Citation reference guard + confidence override
- **Phase 4.0**: V4 Agent multi-turn dialogue (conversation memory + audit)
- **Phase 4.1**: Controlled tool calling (server-side tool registry)
- **Phase 6**: Frontend Engineering Console
  - Vanilla JS ES modules + hash router (zero npm, zero build, zero node_modules)
  - 6 pages: Auth, Groups, Documents, Jobs, RAG, Conversations
  - Permission-aware UI, chat interface, RAG demo
- **Phase 7**: Agent Orchestration ← implemented, under review
  - 3 tables (`agent_runs`, `agent_steps`, `agent_memories`), 8 API endpoints
  - Tool registry: 3 tools with role requirements and risk flags
  - Lightweight state machine (plan→execute→conclude), zero framework dependency
  - Human-in-the-loop: user confirm/reject via API
  - 10 tests written, awaiting full verification (slow SQLite fixture — see pitfall log)
  - 7.5 (Agent eval set) not started

**Verified test baseline**: Backend not re-tested (zero backend changes). Alembic head: `0008_v7_agent_orchestration`. 17 tables.

**Phase 6.6 — Frontend Redesign Round 1 delivered (2026-06-13)**:
- CSS tokens: teal/amber warm palette, type scale, spacing/shadows, 400+ lines. All old pages inherit new look.
- Auth page: tabbed Sign In / Register, 🔦 brand, tagline, registration feedback, post-login routing.
- Onboarding page: guided first-use workspace creation → auto-navigate to Knowledge.
- Ask page (`#/ask`): new home. Question → answer with confidence bar, citation cards, gaps, next steps. Empty state.
- Navbar: Ask / Knowledge / Conversations / Workspace. No Jobs/RAG nav items.
- `esc.js`: shared utility, `answer-card.js`: reusable component.
- Old pages preserved: rag.js, jobs.js, groups.js, documents.js, conversations.js all functional.
- Zero backend changes. Zero npm/build deps.
- `verify_ui.py` 12/12 Playwright tests pass (auth brand, register, onboarding, documents, ask, conversations, workspace, old RAG, old jobs, old documents, logout, re-login→ask).

Phase 5 operational readiness delivered:
- `/health` returns DB connectivity + provider status
- `X-Request-ID` middleware for request tracing
- Smoke playbook: 4-chain verification (RAG, Conversation, Agent, Console)

Phase 6.5 E2E tests delivered:
- 3 Playwright browser tests: Auth→Groups, Document Upload, RAG Answer
- uvicorn subprocess fixture with SQLite + alembic auto-migration
- **109 tests total** (106 backend + 3 E2E), ruff clean
- Frontend bug fix: `/auth/me` now returns `group_name`, frontend uses `group_id`/`group_name`
- Frontend bug fix: navbar group selector uses `setState()` (not direct mutation)
- Frontend bug fix: documents page uses non-empty search query default

Frontend UX polish delivered (2026-06-13):
- CSS: deleted V1 legacy (~100 lines), fixed .topbar duplicate, added spinner/emptyState/errorCard/toast/tableHover
- Pages: all 6 pages have pageTitle, spinner loading, unified empty states
- Navbar: active link highlighting, setState for group selector
- Toast: success/error notifications (3s auto-dismiss)
- buttons: disabled state styling
- 109 tests pass, 5/6 pages browser-verified

Frontend Redesign Round 1 delivered (2026-06-13):
- See Phase 6.6 entry above for full scope
- 12/12 browser smoke tests pass via verify_ui.py
- R1 acceptance complete — ruff clean, manual smoke checklist in plan §10
- Code review: APPROVED, 5/7 findings fixed
- E2E: tests/e2e/test_console_e2e.py updated for R1 flow (4 test chains, needs live server)
- Codemap: docs/CODEMAPS/frontend.md updated

**R1 Verification**: ruff clean, verify_ui.py 12/12 passed.

Next priority: Cloud deployment to ECS, then Round 2 (Knowledge merge, Conversations two-panel).

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
- `POST /groups/{group_id}/conversations`
- `GET /groups/{group_id}/conversations`
- `GET /groups/{group_id}/conversations/{id}`
- `POST /groups/{group_id}/conversations/{id}/messages`

## Verification Status

Latest local verification:

```text
2026-06-12 09:00:00 +08:00

Command:
.\.venv\Scripts\python -m pytest -p no:cacheprovider --basetemp=.tmp/pytest-temp

Result:
96 passed, 1 warning

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
0007_v4_conversations (head)
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
