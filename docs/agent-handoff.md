# Agent Handoff Snapshot

Last updated: 2026-06-18

## Current Phase

**Phases 0–7 delivered; current focus is Phase 8 Experience Integration** — see `docs/project-roadmap.md`.

**Product north star updated 2026-06-18**: Semantic Lighthouse is an ontology-oriented semantic operating layer workspace for enterprise AI transformation. It helps enterprises turn fragmented knowledge, documents, systems, and workflows into a permission-aware, auditable, actionable Ontology semantic layer that can be safely used by applications and Agent workflows.

In this project, Ontology means business objects, properties, relationships, actions, permissions, evidence, and Agent-facing interfaces. The current trusted RAG / task / Agent loop is the foundation, not the destination.

**Current sequencing**:

```text
Phase 8: RAG -> user-confirmed task -> Agent/HITL -> audit
Phase 9: schema/frontmatter validation -> entity extraction -> wikilink relation extraction -> broken-link detection -> ontology graph/entity detail
```

Do not start Phase 9 by building a full modeling studio, Graph RAG, or Agent auto-write path. Phase 9 starts with read-only governance and graph visibility.

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

**Verified test baseline**: 207 pytest passed, ruff clean, alembic `0011` at head, production safety checks delivered. verify_ui 17/19 (2 known-fragile on fake chat timing).

### Agent Workflow Evaluation v1 (2026-06-17) — delivered

- **17 agent tests** covering 7 scenarios: tool execution, risky confirmation, risky rejection (side-effect verification), role denial, unregistered tool rejection, audit completeness, cross-group isolation.
- Fixes: `is_risky` enforcement (was defined but never checked), error→status mapping (Error: → step.status=failed), `?tool=` eval param (whitelist-gated).
- See `docs/agent-eval-report.md` for full results.

### Knowledge Governance v1 (2026-06-17) — delivered

- **Archive audit**: `archived_by`, `archived_at`, `archive_reason` (migration `0011`).
- **`GET /documents?status=`** server-side filter.
- **Frontmatter metadata**: entityType/source/ontology status badges in document list, click-to-expand metadata panel.
- **Documentation drift note**: an earlier handoff referenced `docs/kgov-v1-report.md`, but that file is not present in the repository. Treat this as a Phase 9 governance input, not a delivered report.

### Agent Audit Hardening (2026-06-18) — delivered

Three production safety fixes — no new Agent capabilities, no framework changes:

1. **Shared document lifecycle** (`services/document_lifecycle.py`): `archive_document` helper enforces group_id, status gate, and writes `archived_by` / `archived_at` / `archive_reason`. Both REST endpoint and Agent tool path reuse the same helper. Agent tool previously only set `status="archived"`, bypassing audit fields.

2. **HITL audit event persistence** (`routers/agent.py`): User confirm/reject responses are now appended as separate `AgentStep` records instead of overwriting the original `ask_user` step. Each response step carries `user_id`, `response`, `confirmed`/`rejected`, `tool`, `arguments`, and `responded_at`. Original ask_user step is preserved as the system's confirmation request.

3. **Production safety defaults** (`config.py`): New `APP_ENV` field (default `development`). `Settings.validate_runtime_safety()` checks in production mode: `JWT_SECRET_KEY` ≠ default placeholder, ≥ 32 chars, `COOKIE_SECURE=true`, `DATABASE_URL` ≠ default dev connection. Fails closed — errors are clear, secrets are never logged.

- **Tests**: 6 audit tests (`test_agent_audit.py`) + 6 config tests (`test_config.py`). Full suite: 207 passed, ruff clean.
- **Engineering judgment**: Agent tools must not bypass deterministic backend audit; user confirmation itself is an audit event; production defaults must fail closed.

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
5. source_type expanded to `rag_run`, `conversation`, `agent_run`, `manual` (Phase 8.3, commit `f703c7a`).
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

**Phase 8.3 delivered (source_type = rag_run | conversation | agent_run | manual). Still deferred**:
- Manual task creation UI, independent detail page route, task edit modal, edit/delete by non-creator.

### Product Alignment (2026-06-18)

- New product boundary source: `docs/product-alignment-prd.md`.
- Current positioning updated 2026-06-18: Semantic Lighthouse is an ontology-oriented semantic operating layer workspace for enterprise AI transformation.
- Ontology definition: business objects, properties, relationships, actions, permissions, evidence, and Agent-facing interfaces. It is not just a knowledge graph or RAG document library.
- Current near-term workflow: RAG answer -> inspect citations/confidence/gaps -> user-confirmed task -> Agent/HITL -> audit.
- Next major phase: Phase 9 Ontology Core v1 starts with schema/frontmatter validation, entity extraction, wikilink relation extraction, broken-link detection, ontology graph, and entity detail.
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

**Next priority**: V2.3 real DeepSeek smoke result recording; Agent eval report refinement; decide V2.4 scope.

### Agent Capability v2.1 — LLM Tool Loop (2026-06-17) — delivered

**Commit**: `78c3d9a` — 23 agent tests, ruff clean.

**What was built**:

- **`AgentDecision`**: call_tool / finalize dual-action dataclass (`agent_orchestrator.py`)
- **`agent_loop()`**: while loop + LLM decide + tool execute + observe + max_steps gate + risky pause + consecutive error detection. ~100 lines.
- **`FakeLoopChatClient`**: pre-recorded decision sequence with cursor (`chat.py`). `ChatClient.agent_decide()` now implemented for DeepSeek (V2.2).
- **V1/V2 path split**: `?tool=` non-empty → deterministic V1 single-tool path (17 existing tests preserved). `?tool=` empty → V2 agent_loop path.
- **Respond fixes**: `"stop"` keyword → `stopped` status. Risky confirm no longer finalizes — returns to `executing`. Risky reject sets `observation="User REJECTED...Do NOT propose again"`.
- **max_steps**: configurable via `Settings.agent_max_steps` (env AGENT_MAX_STEPS), default 5, capped 1–10 (V2.2).
- **6 new tests**: 4 parametrized (simple, error_retry, max_steps_stopped, two_step) + 2 standalone (risky_confirm_execute, reject_risky_alternative).

**Key decisions**:
1. `?tool=` empty → V2 loop; non-empty → V1 deterministic eval path.
2. max_steps counts all AgentStep types (conservative).
3. FakeLoopChatClient via `ChatClient.agent_decide()` interface — `create_chat_client` mock injects it.

**Remaining risks**: real DeepSeek smoke pending manual terminal run; Agent V2.4 scope TBD.

### Agent Capability V2.3 — Real LLM Smoke & Evaluation (2026-06-18) — delivered

- **Fake-provider eval**: 5 scenarios (finalize, list_documents, archived exclusion, risky confirmation, invalid tool). 39 tests.
- **Real DeepSeek smoke**: `scripts/smoke_agent_deepseek.py` — 3 scenarios, SKIP without key. Validates AgentDecision JSON shape only. Pending manual terminal run with API key.
- **See**: `docs/agent-capability-v23-eval.md` for full scenario table.

### Agent Capability V2.2 — Provider + Audit Hardening (2026-06-18) — delivered

- **DeepSeek agent_decide()**: real /chat/completions call, json_object, v4 thinking disabled. Validates tool_name (non-empty), tool_arguments (must be dict). ChatError on bad parse/validation.
- **ChatError audit**: V2 path catches ChatError → failed step + fail_run → HTTP 502. No Agent run left stuck in executing.
- **AgentDecision.raw_response**: 500-char truncation stored in action_detail.raw_llm_response.
- **plan_json audit**: llm_decision events per step + stopped event on max_steps.
- **Settings.agent_max_steps**: env AGENT_MAX_STEPS, default 5, cap 1–10.
- **Risky action_detail**: requires_confirmation, risk_level, confirmation_reason in both V1/V2 paths.
- **E2E test fix**: dashboard assertion updated for current UI.
- **38 tests**: agent + chat + E2E, ruff clean.

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
- Ontology KB governance drift: `INDEX.md` / `AUTO_INDEX.md` reference `research/...`, but the inspected `F:\ontology-kb\knowledge-graph` workspace currently lacks a `research/` directory.
- Eval drift: `docs/eval/rag-queries-ontology.json` includes expected document IDs that do not exist in the current KB, including `concepts/agent`, `concepts/ontology-sdk`, `vendors/palantir-foundry`, `vendors/huawei-fusioninsight`, `cases/banking-knowledge-graph-customer-360`, and `cases/healthcare-ontology-patient-modeling`.

**Recommended next iteration**:
1. Run real DeepSeek Agent smoke manually and record results in `docs/agent-capability-v23-eval.md`.
2. Build Agent frontend visibility for existing backend (run/step/HITL timeline page).
3. Expand task source traceability beyond `rag_run` (conversation / agent_run / manual).
4. Harden conversation UX: visible citations, tool call display, failure states.
5. Write demo scenario scripts for portfolio presentation.
6. After Phase 8 is demonstrable, start Phase 9 Ontology Core v1 with read-only governance and graph visibility.

**Agent Architecture Research (2026-06-15)**:
- `docs/research/public-agent-architecture-research.md` — 8 public projects analyzed
- Adoption decision recorded in the report: adopt quality-gate docs, project workflow docs, handoff/codemap maintenance, prompt archive discipline, and manual review-before-commit now.
- Later: Tool Registry + risk labels, Agent eval set, structured handoff payloads, and conversation context condensation.
- Deferred: Auto Memory, Auto Commit, Docker sandbox, event sourcing rewrite, LangGraph/AutoGen integration.
- Decision: Stay with lightweight FSM (no LangGraph), keep learning records human-reviewed, and keep commits intentional while the owner is still learning through diffs.

**Deep Agents / LangGraph Course Review (2026-06-18)**:
- LangChain Deep Agents is useful as an agent-harness reference for planning, context offloading, subagent isolation, HITL, permission rules, and audit-friendly observe/action loops.
- Adopt patterns into the existing implementation: todo-like planning goes into `plan_json`, observable decisions go into `agent_steps`, risky actions keep `awaiting_confirmation`, and rejected risky tools must be written back as observations.
- Do not adopt the LangGraph/Deep Agents runtime now. Current product boundary favors the existing controlled FSM + `agent_loop()`.
- Runtime adoption should be reconsidered only if measured multi-step Agent scenarios show the lightweight loop is insufficient: complex resume, branching, parallel subtask isolation, or context offloading cannot be maintained cleanly with the current database event trail.
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

### Agent Frontend Visibility — Phase 8.2 (2026-06-18)

**Status**: In progress — initial page delivered. Phase 8.2 Agent console has UI smoke coverage (verify_ui check: "Agent page renders" PASS).

- **New page**: `static/js/pages/agent.js` — `#/groups/:gid/agent`
- **Navbar**: "Agent" link added next to "任务"
- **Capabilities delivered**:
  - Create Agent Run: goal input + 3 example goal buttons → `POST /groups/{gid}/agent/runs`
  - Agent Run list: goal, status badge, phase, step count, timestamps → `GET /groups/{gid}/agent/runs`
  - Agent Run detail: run meta, plan_json collapsible, final answer, step timeline → `GET /groups/{gid}/agent/runs/{run_id}`
  - Step timeline: step_index, phase, thought, action_type, status dot, action_detail (collapsible JSON), observation (truncated with expand), error_message, timestamps
  - Execute next step: button for created/planning/executing status → `POST /groups/{gid}/agent/runs/{run_id}/execute`
  - HITL confirm/reject/stop: confirmation card with warning → `POST /groups/{gid}/agent/runs/{run_id}/respond`
  - Status-aware UI: completed shows final_answer, failed shows error, stopped shows stopped message, awaiting_confirmation shows risk warning
  - User audit: confirm/reject response steps visible in timeline with user tags
- **Not in scope**: conversation_id selection, multi-Agent, web search, LangGraph, DB migrations
- **Verification**: 37 agent tests pass, ruff clean, verify_ui 18/21 (3 pre-existing failures unrelated to Agent page)

**Next on Phase 8**: 8.1 real DeepSeek smoke recording. Then Phase 9 Ontology Core v1 — start with KB governance input before entity extraction or graph UI.

### Demo Scenario Scripts — Phase 8.5 (2026-06-18)

**Status**: Delivered.

- **`docs/interview-demo-questions.md`**: Full rewrite. Replaced "enterprise RAG/Agent prototype" framing with Ontology semantic operating layer narrative.
  - Added 北极星开场 (North Star Opener)
  - Phase 8 full-loop demo: 8.0 知识导入与权限隔离 → 8.1 RAG citation/confidence/gap → 8.2 证据不足 → 8.3 用户确认任务 → 8.4 多轮对话 → 8.5 Agent/HITL/Audit → 8.6 生产安全
  - Phase 9 Teaser: Ontology Core v1 planned items (not built)
  - Two-minute quick demo script
  - Closing line emphasizes Ontology destination over RAG/Agent framing

### Conversation UX Hardening — Phase 8.4 (2026-06-18)

**Status**: Delivered.

- **`static/js/pages/conversations.js`**: Rewritten with structured message rendering
  - `renderUserMessage` / `renderAssistantMessage` / `renderToolMessage` functions
  - Assistant: content + confidenceBadge + context bar (🔍 retrieval method · 📄 N 条引用 · model) + citations list (title, snippet, score, retrieval method) + knowledge_gaps list
  - Tool: tool name + arguments + result summary (300-char truncate with expand)
  - User: kept simple
  - Send button: disabled during send ("发送中..."), restored on error with clear Chinese error message
  - Load error: styled panel instead of bare error text
  - Now imports `esc` from `../util/esc.js` and `confidenceBadge` from `../components/badge.js`
- **Cleanup**: models.py Task docstring, product-alignment-prd.md Phase 8 gap list, agent-handoff.md old "V1 only rag_run" text — all updated
- **Verification**: verify_ui 19/22 (Conversations renders PASS, 3 pre-existing failures unrelated), test_tasks.py 22/22 PASS, ruff clean

### Task Source Type Expansion — Phase 8.3 (2026-06-18)

**Status**: Delivered.

- **Schema**: `TaskCreateRequest.source_type` expanded from `^rag_run$` to `^(rag_run|conversation|agent_run|manual)$`
- **Router docstring**: Updated to reflect all 4 source types
- **Tests**: 22 task tests pass (added parametrized test for conversation/agent_run/manual create; invalid-type test covers "", "invalid", "unknown")
- **Frontend**: `tasks.js` already has Chinese labels for all 4 source types; non-rag_run sources show "暂不支持预览此来源类型"
- **Not in scope**: manual task creation UI, task editor, delete endpoint, DB migration
- **Verification**: 22/22 task tests pass, ruff clean

## Development Workflow Update (2026-06-18)

The project has adopted a **three-lane tiered iteration workflow** (`docs/development-workflow.md`):

- **Fast Lane** — docs, prompts, minor UI copy/CSS, non-core test fixes. Verify: `git diff --check`, `git status --short`, minimal format check only. No full pytest, no handoff update, no engineering memory.
- **Standard Lane** — normal backend/frontend features, routine tests. Verify: related pytest, ruff on changed files. Short plan, commit. No full handoff/memory update on every micro-edit.
- **Safety Lane** — auth, permissions, group_id isolation, Agent writes, RAG, document lifecycle, production config, migrations, security audit. Full pytest, ruff, risk description, handoff update, engineering memory update.

Every iteration must begin with a lane declaration: `Lane: Fast / Standard / Safety` + one-line reason.

The goal is to reduce process overhead on low-risk changes and reserve deep verification for high-risk work.

## Phase 8 Checkpoint Review (2026-06-18)

**Conclusion**: No direction drift. Phase 8 is on track. Two documentation inconsistencies found and fixed.

### Findings

| Severity | Issue | Action |
|----------|-------|--------|
| HIGH | Roadmap 8.2 not marked ✅ despite Agent console being delivered with UI smoke | Fixed: 8.2 marked ✅ |
| HIGH | Phase 7 gap text said "missing frontend visibility" — stale after 8.2 | Fixed: updated to reflect Agent console delivered |
| MEDIUM | `test_conversations.py`: 19/20 tests ERROR with Windows `PermissionError` on temp dir — pre-existing, confirmed on clean HEAD | Recorded as known issue; not a Phase 8 regression |
| MEDIUM | Roadmap metrics said `verify_ui 17/19` — actual is 19/22 (new checks added for Agent page, cancelled tab, etc.) | Fixed: updated to 19/22 with failure descriptions |
| LOW | Phase 4 "Next" text listed UX hardening as future work — done in 8.4 | Fixed: updated to reflect 8.4 delivered |
| LOW | `agent-capability-v2-design.md` and `highlight-log.md` contain old "knowledge evidence workspace" phrasing | Historical docs, not current entry files. No action needed. Recorded. |

### Verified Boundaries

- **Ontology direction**: All entry files (AGENTS.md, CLAUDE.md, PRODUCT.md, PRD) consistently point to Ontology semantic operating layer. No drift back to generic RAG/Agent.
- **Phase 9**: Correctly described as NEXT phase with governance inputs. Not described as delivered.
- **Permission/audit**: Task source_type expansion preserves group_id isolation (22 tests). Agent boundary remains controlled HITL. Agent cannot auto-write Ontology entities.
- **Demo loop**: `docs/interview-demo-questions.md` covers full Phase 8 flow: RAG → task → Agent/HITL → audit.

### Known Risks (unchanged)

- KB broken links: `research/` directory missing, eval gold doc IDs inconsistent with real files
- `docs/kgov-v1-report.md` referenced but not present in repo
- `test_conversations.py` blocked by Windows temp dir PermissionError (19 tests)
- Real DeepSeek Agent smoke pending (Phase 8.1)

## Agent Instructions For The Next Session

Start by reading `AGENTS.md`, `PRODUCT.md`, `docs/product-alignment-prd.md`, `CLAUDE.md`, this handoff, and the latest engineering memory files. Then run review and tests according to `docs/development-workflow.md` before changing code.

Do not frame the project as only a RAG/Agent portfolio. The current product direction is Ontology semantic operating layer. Phase 8 should finish the demonstrable RAG -> task -> Agent/HITL -> audit loop; Phase 9 should begin with read-only ontology governance and graph visibility.

Do not rely on chat history. The latest verified baseline before this handoff refresh was commit `d45bef4 docs: refresh project handoff entrypoints`; the working tree should be clean before the next iteration.
