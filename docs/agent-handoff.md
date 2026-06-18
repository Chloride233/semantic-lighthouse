# Agent Handoff Snapshot

Last updated: 2026-06-18

## Current Phase

**Phases 0–7 delivered** — see `docs/project-roadmap.md`.

- **Phase 3**: RAG quality review with real ontology KB ← **P4 delivered 2026-06-15**
  - 74 real ontology documents imported from `F:\ontology-kb\knowledge-graph`
  - 10-question quality eval: 20/20 Chinese, 20/20 forbidden-clean, 20/20 audit-complete
  - Chinese bi-gram keyword search + ASCII-weighted relevance
- **Phase 4.0/4.1**: Conversations + tool calling
- **Phase 6**: Frontend — all Chinese, zero encoding issues, 13/13 UI smoke
- **Phase 7**: Agent Orchestration — 7.1–7.5 delivered (17 agent tests, 7 eval scenarios). See `docs/agent-eval-report.md`. Agent Capability v2 LLM tool loop design in `docs/agent-capability-v2-design.md`, reviewed in `docs/agent-capability-v2-review.md`.
- **Cloud deployment**: Tencent Cloud Lighthouse verified 2026-06-16
  - Ubuntu Server 24.04 LTS Docker CE image, 4 vCPU / 4 GiB RAM / 40 GiB system disk
  - Deployment path: `/opt/semantic-lighthouse`
  - `semantic-lighthouse-api` and `semantic-lighthouse-postgres` healthy via production Compose
  - Alembic migrated through `0009_v9_rag_audit`
  - `scripts/deploy/smoke-cloud.sh` passed with keyword RAG and `citation_count: 1`
  - Public `/health`, `/docs`, and `/console` reachable through temporary TCP `8000` demo access

**Verified test baseline**: 175+ pytest, ruff clean, alembic `0011` at head, verify_ui 17/19 (2 known-fragile on fake chat timing).

### Agent Workflow Evaluation v1 (2026-06-17) — delivered

- **17 agent tests** covering 7 scenarios: tool execution, risky confirmation, risky rejection (side-effect verification), role denial, unregistered tool rejection, audit completeness, cross-group isolation.
- Fixes: `is_risky` enforcement (was defined but never checked), error→status mapping (Error: → step.status=failed), `?tool=` eval param (whitelist-gated).
- See `docs/agent-eval-report.md` for full results.

### Knowledge Governance v1 (2026-06-17) — delivered

- **Archive audit**: `archived_by`, `archived_at`, `archive_reason` (migration `0011`).
- **`GET /documents?status=`** server-side filter.
- **Frontmatter metadata**: entityType/source/ontology status badges in document list, click-to-expand metadata panel.
- **Document governance report**: `docs/kgov-v1-report.md`.

### RAG Quality Evaluation v1 — Eval Harness (2026-06-17) — delivered

**Plan**: merged from `.tmp/rag-quality-v1-review-a/b/c/d` (4-window review)

- **`docs/eval/rag-queries-ontology.json`**: 24 Chinese ontology-KB questions × 7 types with document-level annotations.
- **`docs/eval/rag-queries-self-test.json`**: preserved 16 system self-test queries (renamed from `rag-queries.json`).
- **`scripts/run_eval.py`**: +MRR, +Precision@5, +`--output`/`--markdown` flags.
- **`scripts/check_eval_thresholds.py`** (new): keyword Recall@5 ≥ 0.6 gate + `--baseline` regression compare.
- **`docs/rag-quality-eval-report.md`**: thin report template.

Manual gates:
```powershell
.\.venv\Scripts\python scripts/run_eval.py --output .tmp\retrieval_eval_report.json --markdown .tmp\retrieval_eval_report.md
.\.venv\Scripts\python scripts\check_eval_thresholds.py .tmp\retrieval_eval_report.json
```

### Product Alignment A.3 — Lightweight Task Board (2026-06-17) — delivered

**Plan**: `.claude/plans/lightweight-task-board.plan.md`
**Parallel reviews**: `.tmp/parallel-taskboard-reviews.md` (A/B/C/D windows, merged)

**What was built**:

- **`tasks` table** (migration `0010_v10_tasks`): `id`, `group_id`, `title`, `description`, `status` (pending/in_progress/done/cancelled), `source_type` (V1: rag_run only), `source_id`, `created_by`, timestamps.
- **4 API endpoints**: `POST /groups/{gid}/tasks` (create), `GET /groups/{gid}/tasks` (list + status filter), `GET /groups/{gid}/tasks/{id}` (detail), `PATCH /groups/{gid}/tasks/{id}` (update status by any member, title/desc by creator only).
- **No DELETE endpoint** — V1 preserves audit trail. V2 will add `status: 'cancelled'` soft-delete.
- **Frontend**: "✓ 确认任务" button in answer-card (`showConfirm` param), new `/tasks` board page with status filter tabs + task cards with color bars, "任务" navbar entry.
- **15 new pytest tests** (create/list/update/isolation/permissions/no-delete gate).
- **4 new verify_ui checks** (tasks empty state, filter tabs, confirm button existence, navbar entry).

**Key design decisions** (user-confirmed):
1. DELETE removed from V1 — audit trail over cleanup convenience.
2. Owner/Admin cannot edit others' task title/description — creator-only semantics.
3. Migration named `0010_v10_tasks.py` — aligns with existing `v<N>` convention.
4. verify_ui check 15 is button-existence only (not full click flow) — full E2E deferred to Playwright.
5. V1 source_type only supports `rag_run`. conversation/agent_run/manual deferred.
6. Manual task creation deferred to V1.1.
7. No task comments, attachments, due dates, priorities, assignees, or external integrations.

### v1.1 — Source Traceability + Soft Cancel (2026-06-17) — delivered

**Plan**: `.claude/plans/actionable-rag-v11.plan.md` (from merged `.tmp/actionable-rag-v11-reviews.md`)

**What was built**:

- **`status=cancelled`**: soft cancel (not delete). Schema pattern extended `^(pending|in_progress|done|cancelled)$`. No DB migration needed. Cancelled tasks retain full detail/visibility, can be reopened to `pending`.
- **Source traceability**: click any task card to inline-expand source RAG run detail. Calls existing `GET /rag/runs/{source_id}` — no new API. Shows original question, answer (via `answerCard` with `hideNextSteps: true`), retrieval metadata, and link to RAG debug console.
- **CSS variable fix**: added `--brand-teal`, `--brand-amber`, `--brand-blue`, `--ok-strong`, `--border`, `--surface`, `--text-secondary`, `--text-muted`, `--radius`, `--duration-fast` aliases to `:root`. Fixes silently-broken task board styling.
- **5 new tests**: cancelled CRUD + member reopen + non-member detail isolation.
- **2 new verify_ui checks**: task card render + cancelled filter tab.

**Still deferred to v1.2+**:
- Manual task creation, conversation/agent_run source_type, independent detail page route, task edit modal, edit/delete by non-creator.

### Product Alignment (2026-06-17)

- New product boundary source: `docs/product-alignment-prd.md`.
- Current positioning: Semantic Lighthouse is a permission-aware knowledge evidence workspace for enterprise AI transformation.
- Core near-term workflow: ask question -> inspect citations/confidence/gaps -> review next steps -> user confirms selected next steps into lightweight tasks.
- Agent boundary: Agent is a controlled coordination layer for multi-step/tool-based/auditable workflows, not a replacement for deterministic backend rules.
- Web search status: Discovery only. Validate with low-confidence questions before promoting it into the core product flow.

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

**Next priority**: Agent Capability V2.2 — DeepSeek agent_decide + real LLM smoke. See `docs/agent-capability-v2-design.md` and `docs/agent-capability-v2-review.md`.

### Agent Capability v2.1 — LLM Tool Loop (2026-06-17) — delivered

**Commit**: `78c3d9a` — 23 agent tests, ruff clean.

**What was built**:

- **`AgentDecision`**: call_tool / finalize dual-action dataclass (`agent_orchestrator.py`)
- **`agent_loop()`**: while loop + LLM decide + tool execute + observe + max_steps gate + risky pause + consecutive error detection. ~100 lines.
- **`FakeLoopChatClient`**: pre-recorded decision sequence with cursor (`chat.py`). `ChatClient.agent_decide()` abstract method for V2.2 real providers.
- **V1/V2 path split**: `?tool=` non-empty → deterministic V1 single-tool path (17 existing tests preserved). `?tool=` empty → V2 agent_loop path.
- **Respond fixes**: `"stop"` keyword → `stopped` status. Risky confirm no longer finalizes — returns to `executing`. Risky reject sets `observation="User REJECTED...Do NOT propose again"`.
- **max_steps=5**: counts all non-think AgentStep types. Hard-configured; `Settings.agent_max_steps` deferred to V2.2.
- **6 new tests**: 4 parametrized (simple, error_retry, max_steps_stopped, two_step) + 2 standalone (risky_confirm_execute, reject_risky_alternative).

**Key decisions**:
1. `?tool=` empty → V2 loop; non-empty → V1 deterministic eval path.
2. max_steps counts all AgentStep types (conservative).
3. FakeLoopChatClient via `ChatClient.agent_decide()` interface — `create_chat_client` mock injects it.

**Remaining risks**: no real LLM tool decisions (fake only), `Settings.agent_max_steps` not configurable, `plan_json`/`raw_llm_response` audit not stored. See design doc §17.

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
2026-06-17

Command:
.\.venv\Scripts\python -m pytest -p no:cacheprovider

Result:
175+ passed (17 agent, 20 task, 25+ document, 28+ RAG, 11+ retrieval)

Command:
.\.venv\Scripts\python scripts\verify_ui.py

Result:
17 passed, 2 failed (known-fragile on fake chat timing)

Command:
.\.venv\Scripts\python -m ruff check src tests scripts

Result:
All checks passed!

Command:
.\.venv\Scripts\python -m alembic upgrade head && .\.venv\Scripts\python -m alembic current

Result:
0011_v11_document_archive_audit (head)
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
1. Agent Capability V2.1: LLM tool loop (agent_loop + FakeLoopChatClient + 6 parametrized tests). See `docs/agent-capability-v2-review.md` for preconditions.
2. V2.2: DeepSeek agent_decide + smoke; V2.3: 5 real LLM eval scenarios.
3. Deep Agents pattern review: borrow todo/planning, context offloading, subagent isolation, HITL, and event-flow ideas only where they fit the existing lightweight FSM.
4. V1.2 (task system): manual task creation + `ConversationMessage.next_steps`.
5. Continue retrieval-quality hardening.

**Agent Architecture Research (2026-06-15)**:
- `docs/research/public-agent-architecture-research.md` — 8 public projects analyzed
- Adoption decision recorded in the report: adopt quality-gate docs, project workflow docs, handoff/codemap maintenance, prompt archive discipline, and manual review-before-commit now.
- Later: Tool Registry + risk labels, Agent eval set, structured handoff payloads, and conversation context condensation.
- Deferred: Auto Memory, Auto Commit, Docker sandbox, event sourcing rewrite, LangGraph/AutoGen integration.
- Decision: Stay with lightweight FSM (no LangGraph), keep learning records human-reviewed, and keep commits intentional while the owner is still learning through diffs.

**Deep Agents / LangGraph Course Review (2026-06-18)**:
- LangChain Deep Agents is useful as an agent-harness reference for planning, context offloading, subagent isolation, HITL, and audit-friendly observe/action loops.
- Do not adopt the LangGraph/Deep Agents runtime now. Current product boundary favors the existing controlled FSM + planned LLM tool loop.
- Runtime adoption should be reconsidered only if measured multi-step Agent scenarios show the lightweight loop is insufficient.
- See `docs/project-roadmap.md` Phase 7 follow-up and `docs/agent-capability-v2-design.md` section 14.

**Workflow docs added (2026-06-16)**:
- `docs/quality-gate.md` — gate levels for docs, backend, frontend, migrations, and full regression.
- `docs/project-workflows.md` — repeatable workflows for iteration, review, RAG quality, frontend, and deployment.

**Citation Quantity And Quality Improvement (2026-06-16)**:
- `POST /groups/{group_id}/rag/answer` already supported `limit`; frontend knowledge问答 and RAG调试台 now expose 5/8/10 citation choices.
- Citation assembly now filters empty/zero-score candidates and prioritizes document diversity before overflowing repeated chunks from the same document.
- Conversation messages can pass `limit`; current console sends 8 for multi-turn chat.
- Verification: `pytest` full suite `146 passed`; `scripts/verify_ui.py` `13 passed`.

**Web Search Evidence Tool Design (2026-06-17)**:
- Design doc added: `docs/web-search-design.md`.
- Decision: treat web search results as auditable external Evidence, not raw text pasted into the model.
- Initial provider recommendation: Firecrawl first, behind a provider interface with fake tests; Tavily/Exa can be added later if needed.
- Implementation boundary: start with read-only web search API and separate UI panel; do not auto-ingest web pages into the group knowledge base.

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
