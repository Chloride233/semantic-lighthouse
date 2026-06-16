# Agent Handoff Snapshot

Last updated: 2026-06-15

## Current Phase

**Phases 0–7 delivered** — see `docs/project-roadmap.md`.

- **Phase 3**: RAG quality review with real ontology KB ← **P4 delivered 2026-06-15**
  - 74 real ontology documents imported from `F:\ontology-kb\knowledge-graph`
  - 10-question quality eval: 20/20 Chinese, 20/20 forbidden-clean, 20/20 audit-complete
  - Chinese bi-gram keyword search + ASCII-weighted relevance
- **Phase 4.0/4.1**: Conversations + tool calling
- **Phase 6**: Frontend — all Chinese, zero encoding issues, 13/13 UI smoke
- **Phase 7**: Agent Orchestration — 7.5 (Agent eval set) not started

**Verified test baseline**: 125 pytest, ruff clean, alembic `0009` at head, 17 tables. scan_encoding OK, verify_ui 13/13.

### P1 RAG Output Contract Fix (2026-06-14) — delivered

- Chinese system prompt with explicit English-phrase prohibitions.
- Frontend confidence: `unknown` state, no dead `confidence_score`, no enum leak.
- 3 contract tests.

### P2 QA Audit & Citation Tracking (2026-06-14) — delivered

**Migration `0009_v9_rag_audit`**: added `status`, `error_message`, `duration_ms`, `retrieved_count` to `rag_runs`.

**Three paths all audited**:
| Path | status | Persisted |
|------|--------|-----------|
| no evidence | `no_evidence` | ✅ |
| success | `success` | ✅ |
| ChatError | `error` | ✅ (was ❌ — largest gap) |

**New tests**: `test_rag_run_includes_audit_fields`, `test_failed_rag_run_is_persisted_and_isolated`, `test_no_evidence_run_has_correct_audit_status`. 22 RAG tests total.

### P3 Retrieval Eval + Frontend Encoding Verification (2026-06-14) — delivered

- **P3 eval**: 15 seed docs, 20 queries, `scripts/run_eval.py`, reproducible (fake embeddings).
- **Encoding**: All `static/` and `scripts/` files verified UTF-8 clean — no `U+FFFD`, no mojibake.
- **`scripts/scan_encoding.py`**: CI guard — fails on garbled characters.
- **`scripts/verify_ui.py`**: ruff clean, 13/13 UI smoke passes.
- **Browser screenshots confirmed**: CSS, Chinese text render correctly.

**Next priority**: P4 Agent eval or cloud deployment — owner's choice.

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

New eval tools:
- `scripts/run_rag_quality_eval.py` — imports real ontology KB, runs 10 questions, validates contract

## Verification Status

Latest local verification:

```text
2026-06-14

Command:
.\.venv\Scripts\python -m pytest -p no:cacheprovider --basetemp=.tmp/pytest-temp --ignore=tests/e2e

Result:
113 passed, 1 warning

Command:
.\.venv\Scripts\ruff check src tests

Result:
All checks passed!

Command:
DATABASE_URL="sqlite+pysqlite:///./.tmp/test-migration.db"
.\.venv\Scripts\python -m alembic upgrade head
.\.venv\Scripts\python -m alembic current

Result:
0009_v9_rag_audit (head)
```

## Current Risks And Next Priority

**P4 RAG Quality Review completed (2026-06-15)**:
- Real ontology KB imported (74 docs), 10-question eval run.
- Chinese bi-gram keyword search + ASCII-weighted relevance ranking.
- `scripts/run_rag_quality_eval.py` for reproducible eval.
- Full report: `docs/engineering-memory/rag-quality-review-2026-06-15.md`.

**Known remaining risks**:
- PDF parsing: extractable text only, no OCR.
- DOCX parsing: ordinary paragraphs only, no tables/headers/footers.
- No token usage / latency / cost tracking in rag_runs or conversation_messages.
- No max concurrent upload session limit per user/group.
- `read_bytes()` on final parse step — fine for 50 MiB but monitor on 2 GiB ECS.

**Recommended next iteration**:
1. Set `DEEPSEEK_API_KEY` → re-run quality eval with real LLM answers.
2. Agent eval set (Phase 7.5) — multi-step task scenarios.
3. Cloud deployment with real embedding provider.
4. Add citation score cutoff filter — hide citations below threshold.
5. Log LLM token usage from provider response.

**Agent Architecture Research (2026-06-15)**:
- `docs/research/public-agent-architecture-research.md` — 8 public projects analyzed
- Adoption decision recorded in the report: adopt quality-gate docs, project workflow docs, handoff/codemap maintenance, prompt archive discipline, and manual review-before-commit now.
- Later: Tool Registry + risk labels, Agent eval set, structured handoff payloads, and conversation context condensation.
- Deferred: Auto Memory, Auto Commit, Docker sandbox, event sourcing rewrite, LangGraph/AutoGen integration.
- Decision: Stay with lightweight FSM (no LangGraph), keep learning records human-reviewed, and keep commits intentional while the owner is still learning through diffs.

**Workflow docs added (2026-06-16)**:
- `docs/quality-gate.md` — gate levels for docs, backend, frontend, migrations, and full regression.
- `docs/project-workflows.md` — repeatable workflows for iteration, review, RAG quality, frontend, and deployment.

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

P1 (output contract) and P2 (QA audit) are done. Next priority is P3 retrieval eval harness: gold Q&A pairs, recall@k metrics. No new tables needed — the audit trail is already in place.
