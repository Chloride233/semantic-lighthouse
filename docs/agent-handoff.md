# Agent Handoff Snapshot

Last updated: 2026-06-16

## Current Phase

**Phases 0–7 delivered** — see `docs/project-roadmap.md`.

- **Phase 3**: RAG quality review with real ontology KB ← **P4 delivered 2026-06-15**
  - 74 real ontology documents imported from `F:\ontology-kb\knowledge-graph`
  - 10-question quality eval: 20/20 Chinese, 20/20 forbidden-clean, 20/20 audit-complete
  - Chinese bi-gram keyword search + ASCII-weighted relevance
- **Phase 4.0/4.1**: Conversations + tool calling
- **Phase 6**: Frontend — all Chinese, zero encoding issues, 13/13 UI smoke
- **Phase 7**: Agent Orchestration — 7.5 (Agent eval set) not started
- **Cloud deployment**: Tencent Cloud Lighthouse verified 2026-06-16
  - Ubuntu Server 24.04 LTS Docker CE image, 4 vCPU / 4 GiB RAM / 40 GiB system disk
  - Deployment path: `/opt/semantic-lighthouse`
  - `semantic-lighthouse-api` and `semantic-lighthouse-postgres` healthy via production Compose
  - Alembic migrated through `0009_v9_rag_audit`
  - `scripts/deploy/smoke-cloud.sh` passed with keyword RAG and `citation_count: 1`
  - Public `/health`, `/docs`, and `/console` reachable through temporary TCP `8000` demo access

**Verified test baseline**: 146 pytest, ruff clean, alembic `0009` at head, scan_encoding OK, verify_ui 13/13.

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

**Next priority**: manually verify the citation-count UI against the real ontology KB, then choose between retrieval-quality hardening, knowledge-base management, Agent eval, or production operations hardening.

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
2026-06-16

Command:
.\.venv\Scripts\python -m pytest -p no:cacheprovider --basetemp=.tmp\pytest-agent

Result:
146 passed, 1 warning

Command:
.\.venv\Scripts\python scripts\verify_ui.py

Result:
13 passed, 0 failed out of 13 tests

Command:
.\.venv\Scripts\ruff check src tests scripts

Result:
All checks passed!

Command:
.\.venv\Scripts\python scripts\scan_encoding.py

Result:
OK: No encoding issues detected

Command:
DATABASE_URL="sqlite+pysqlite:///./.tmp/takeover-migration-20260616.db"
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
1. Run local app and manually verify 5/8/10 citation counts on real ontology KB questions.
2. Add retrieval-quality metrics for citation precision/diversity at different K values.
3. Add lightweight knowledge-base management functions if product workflow needs them.
4. Agent eval set (Phase 7.5) — multi-step task scenarios.
5. Production operations hardening: backup/restore playbook, HTTPS/domain, and security group tightening after demo access.

**Agent Architecture Research (2026-06-15)**:
- `docs/research/public-agent-architecture-research.md` — 8 public projects analyzed
- Adoption decision recorded in the report: adopt quality-gate docs, project workflow docs, handoff/codemap maintenance, prompt archive discipline, and manual review-before-commit now.
- Later: Tool Registry + risk labels, Agent eval set, structured handoff payloads, and conversation context condensation.
- Deferred: Auto Memory, Auto Commit, Docker sandbox, event sourcing rewrite, LangGraph/AutoGen integration.
- Decision: Stay with lightweight FSM (no LangGraph), keep learning records human-reviewed, and keep commits intentional while the owner is still learning through diffs.

**Workflow docs added (2026-06-16)**:
- `docs/quality-gate.md` — gate levels for docs, backend, frontend, migrations, and full regression.
- `docs/project-workflows.md` — repeatable workflows for iteration, review, RAG quality, frontend, and deployment.

**Citation Quantity And Quality Improvement (2026-06-16)**:
- `POST /groups/{group_id}/rag/answer` already supported `limit`; frontend knowledge问答 and RAG调试台 now expose 5/8/10 citation choices.
- Citation assembly now filters empty/zero-score candidates and prioritizes document diversity before overflowing repeated chunks from the same document.
- Conversation messages can pass `limit`; current console sends 8 for multi-turn chat.
- Verification: `pytest` full suite `146 passed`; `scripts/verify_ui.py` `13 passed`.

## Cloud Deployment Memory

Verified Tencent Cloud deployment:

```text
Date: 2026-06-16
Provider: Tencent Cloud Lighthouse
Server: Ubuntu Server 24.04 LTS Docker CE image, 4 vCPU / 4 GiB RAM / 40 GiB system disk
Path: /opt/semantic-lighthouse
Status: API and PostgreSQL containers healthy
Migration: 0009_v9_rag_audit applied
Smoke: scripts/deploy/smoke-cloud.sh passed with one citation
Public demo: /health, /docs, and /console reachable on temporary TCP 8000
```

Known server path:

```bash
/opt/semantic-lighthouse
```

Production compose command:

```bash
sudo docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build
```

Status commands:

```bash
sudo docker compose --env-file .env.production -f docker-compose.prod.yml ps
sudo docker logs semantic-lighthouse-api --tail 100
curl -fsS http://127.0.0.1:8000/health
```

Use `sudo docker compose` unless the deployment user has been added to the `docker` group and has re-logged in.

Cloud smoke playbook:

```text
docs/cloud-smoke-playbook.md
```

Do not store real `DASHSCOPE_API_KEY`, `DEEPSEEK_API_KEY`, database passwords, cookies, or tokens in this file.

## Agent Instructions For The Next Session

Start by reading `AGENTS.md`, `PRODUCT.md`, `CLAUDE.md`, this handoff, and the latest engineering memory files. Then run review and tests before changing code.

Do not rely on chat history. The latest verified baseline before this handoff refresh was commit `d45bef4 docs: refresh project handoff entrypoints`; the working tree should be clean before the next iteration.
