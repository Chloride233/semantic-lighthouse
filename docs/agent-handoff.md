# Agent Handoff Snapshot

Last updated: 2026-06-20 (Frontend F2A delivered — Pilot workspace active. Phase 14 backend COMPLETE. Migration 0023 at head.)

## Current Phase

**Phase 14.1 delivered: Business Pilot Project Foundation** — see `docs/phase14-planning.md`. A group can now contain multiple business pilot projects following the goal → data → model → validate → pilot chain. **Phases 0–13 complete** — full Ontology pipeline from documents through entities/relations/governance/drafts/packages/business_v1 contracts is stable. Old features (RAG, Agent, Ontology drafts, tasks, conversations) remain as parallel capabilities — Phase 14 shifts the product main chain toward guided business pilot projects without removing them.

**MCP planning boundary**: `docs/mcp-agent-boundary-design.md` records a future
read-only gateway candidate after Phase 13. MCP is an Agent-facing adapter, not
the Ontology. No MCP server/client, SDK, dependency, resource, or tool is
implemented. Future runtime requires authenticated caller mapping, server-side
group/role checks, invocation audit, bounded provenance-preserving output, and
no-write enforcement.

**Product north star updated 2026-06-18**: Semantic Lighthouse is an ontology-oriented semantic operating layer workspace for enterprise AI transformation. It helps enterprises turn fragmented knowledge, documents, systems, and workflows into a permission-aware, auditable, actionable Ontology semantic layer that can be safely used by applications and Agent workflows.

In this project, Ontology means business objects, properties, relationships, actions, permissions, evidence, and Agent-facing interfaces. The current trusted RAG / task / Agent loop is the foundation, not the destination.

**Current sequencing**:

```text
Phase 8: RAG -> user-confirmed task -> Agent/HITL -> audit (DELIVERED)
Phase 9: schema/frontmatter validation -> entity extraction -> wikilink relation extraction -> broken-link detection -> ontology graph/entity detail (DELIVERED)
Phase 10: governance issue triage -> curation demo -> graph UX polish -> evidence bridge -> review (DELIVERED)
Phase 11: modeling drafts v1 — Object Type / Property / Link Type / Action Type proposals from governed entities (BACKEND DELIVERED — 11.5 UI deferred, see docs/phase11-planning.md)
Phase 12: quality gates -> accepted-only immutable contract package -> declarative Action permissions -> real demo/review (DELIVERED)
Phase 13: business_v1 profile specification (13.1 DELIVERED) -> deterministic validator (13.2 NEXT) -> compiler/export/pilot/review
```

Phase 9 started with read-only governance and graph visibility (not a full modeling studio, Graph RAG, or Agent auto-write path). Phase 10 operationalized governance findings into a curation pipeline. Phase 11 continues the read-first approach: modeling drafts are human-reviewed proposals, not production schema, and Agent may read/propose but never auto-create/accept/publish.

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

**Remaining risks**: Agent V2.4 scope TBD (real DeepSeek smoke completed Phase 8.1).

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
2026-06-19 (Phase 11.4 human review workflow delivered)

Command:
.\.venv\Scripts\python -m pytest tests/test_ontology_draft_review.py tests/test_ontology_modeling_drafts.py tests/test_ontology_draft_generation.py tests/test_ontology.py -p no:cacheprovider

Result:
125 passed (33 review + 26 draft + 25 generation + 41 ontology)

Command:
.\.venv\Scripts\python -m pytest -p no:cacheprovider --basetemp=.tmp\pytest-phase11-review

Result:
365 passed, 4 failed (pre-existing E2E: auth timing in test_console_e2e.py)

Command:
.\.venv\Scripts\python -m ruff check src tests

Result:
All checks passed!

Command:
.\.venv\Scripts\python -m alembic upgrade head && .\.venv\Scripts\python -m alembic current

Result:
0016_v16_ontology_modeling_drafts (head)
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

**Next iteration**: Phase 13 COMPLETE (all 12 review gates PASS, `docs/phase13-review.md`). Frontend Refactor F1A delivered by CC — Swiss minimalism app shell, persistent group context, workspace-oriented navigation (工作台/知识/Ontology/执行). F1B Ontology internal workspace to follow. Future backend phases (14a Object Runtime, 14b SDK, 14c Contract Refinement, MCP) remain candidates, not pre-committed.

### Phase 11.1+11.2 Review Hardening — Rescan Evidence Lifecycle (2026-06-19)

**Status**: Delivered. Fix: `scan_group()` now preserves draft evidence pointers across rescans.

**Problem found**: `OntologyModelingDraft` FKs to `ontology_entities`/`ontology_relations`/`ontology_validation_issues` would break on rescan — `scan_group()` deletes and rebuilds these tables. In PostgreSQL, strict FK enforcement would block the delete; in SQLite (default FK=OFF), drafts would hold dangling pointers. Plus `evidence_refs` alone could satisfy draft creation, bypassing group-scoped source validation.

**Fix**:
- **Stable-key relink in `scan_group()`**: Before deleting old records, saves stable evidence keys from current drafts (entity: `document_id`, relation: `(source_document_id, target_path, target_label, relation_type)`, issue: `issue_key`). Nulls draft FKs + flush → deletes old records with intermediate flushes (FK-safe order) → rebuilds → relinks drafts to new record IDs. If evidence vanished, source pointer stays null, draft preserved.
- **evidence_refs boundary**: `POST /groups/{gid}/ontology/drafts` now requires at least one `source_*_id`. `evidence_refs` alone rejected (400). Still accepted as supplemental metadata.
- **No migration**: Scan-level relink correctly handles the delete path.

**Tests**: 10 new (26 total draft tests): entity/relation/issue relink, vanished evidence, metadata preservation, rag_run unaffected, cross-group isolation, evidence_refs-only rejection, PRAGMA foreign_keys=ON regression.

**Verification**: 67 related (26 draft + 41 ontology), 307/311 full suite (4 pre-existing E2E), ruff clean, git diff --check clean.

### Phase 11.1+11.2 — Ontology Modeling Drafts Backend Foundation (2026-06-19)

**Status**: Delivered.

- **New model**: `OntologyModelingDraft` (`ontology_modeling_drafts`) — group-scoped, audit-trailed draft proposals for Object Type / Property / Link Type / Action Type. Fields: id, group_id, draft_type, name, description, status (proposed/accepted/rejected), source_entity_id, source_relation_id, source_issue_id, source_rag_run_id, evidence_refs, payload, created_by, created_at, updated_at, reviewed_by, reviewed_at, review_note. No unique constraint on (group_id, draft_type, name).
- **Migration**: `0016_v16_ontology_modeling_drafts.py` — down_revision `0015_v15_ontology_issue_triage`. SQLite/PostgreSQL compatible.
- **API**: `POST /groups/{gid}/ontology/drafts` (owner/admin create proposed draft, validates all source ids in group, 400 on no evidence, 422 on invalid draft_type). `GET /groups/{gid}/ontology/drafts` (member+ read, filters: draft_type, status, source_entity_id, q; limit/offset pagination).
- **Boundaries**: No PATCH/DELETE/review endpoints, no Agent access, no draft generation, no UI, no Graph RAG, no external KB write. Status always starts as `proposed` — accepted/rejected are Phase 11.4.
- **Tests**: 16 new tests in `tests/test_ontology_modeling_drafts.py` (create/read permissions, group isolation, cross-group source rejection, evidence linkage ×4, draft_type/status/q filters, invalid draft_type 422, no-evidence rejection, admin create).
- **Verification**: 297 passed (4 pre-existing E2E failures), ruff clean, migration 0016 at head, git diff --check clean.

### Phase 11.3 — Deterministic Draft Generation (2026-06-19)

**Status**: Delivered.

- **Service**: `src/semantic_lighthouse/services/ontology_drafts.py` — `generate_modeling_drafts(db, group_id, created_by)` generates Object Type / Property / Link Type / Action Type drafts from group-scoped entities, relations, frontmatter, and confirmed governance issues. No LLM, no Agent, no filesystem, no external KB. Also houses `determine_action_type()` (moved from curation demo script).
- **API**: `POST /groups/{gid}/ontology/drafts/generate` — owner/admin only. Returns `DraftGenerationResponse` with `generated_count`, `existing_count`, `skipped_count`, `counts_by_type`. Member → 403. No entities → 400 with guidance to run ontology scan.
- **Generation rules**:
  - Object Type: one per distinct entity_type. Name = entity_type. Source = first entity sorted by (source_path, id). Generation key: `object_type:<type>`.
  - Property: one per (entity_type, frontmatter_field) excluding entityType/documentType. Name = `<EntityType>.<field>`. Generation key: `property:<type>:<field>`.
  - Link Type: one per (source_type, relation_type, target_type) for resolved relations with target_entity_id. Name = `<Src> -> <Tgt> (<rel>)`. Generation key: `link_type:<src>:<rel>:<tgt>`.
  - Action Type: one per action_type for confirmed issues (triage_status=confirmed). Uses `determine_action_type()` for issue→action mapping. Generation key: `action_type:<type>`.
- **Idempotency**: Two-layer dedup — (1) generation_key in payload, (2) (draft_type, normalized name). Never modifies existing drafts' status, payload, or review metadata.
- **Tests**: 25 new tests in `tests/test_ontology_draft_generation.py` covering permissions (owner/admin/member/outsider/no-entities), all 4 draft types, idempotency, manual draft protection, evidence scoping, generation key presence, and response schema.
- **Boundaries**: No LLM, no Agent, no UI, no review/accept/reject, no external KB modification, no new migration, no stale draft cleanup, no PATCH/DELETE/review API. `determine_action_type` moved from script to service — 35 curation demo tests unaffected.
- **Verification**: 332 passed (4 pre-existing E2E failures), ruff clean src+tests+scripts, git diff --check clean. 127 related tests (25 generation + 26 draft + 41 ontology + 35 curation demo).

### Phase 11.4 — Human Review Workflow (2026-06-19)

**Status**: Delivered.

- **Single review**: `POST /groups/{gid}/ontology/drafts/{draft_id}/review` — owner/admin accept or reject a proposed draft. Accepted/rejected drafts are final (one-time audit): re-review returns 409 preserving original reviewer metadata. Rejected requires non-empty review_note (validated at schema level via `@model_validator(mode="after")`).
- **Batch review**: `POST /groups/{gid}/ontology/drafts/review-batch` — atomically accept or reject 1–100 proposed drafts. All-or-nothing: any missing/cross-group ID → 404 with no partial updates; any already-reviewed → 409. Duplicates deduplicated. All drafts receive the same reviewer, reviewed_at, and review_note.
- **Status transitions**: Only `proposed → accepted` and `proposed → rejected` allowed. No reopen, no overwrite, no accepted↔rejected toggle.
- **Permissions**: `require_group_role(..., {"owner", "admin"})`. Member → 403. Outsider → 403. Cross-group draft ID → 404 (no existence leak).
- **Route ordering**: Static `/drafts/review-batch` before dynamic `/drafts/{draft_id}/review` — prevents FastAPI path conflicts.
- **Schemas**: `OntologyModelingDraftReviewRequest`, `OntologyModelingDraftBatchReviewRequest`, `OntologyModelingDraftBatchReviewResponse` — Pydantic v2 `model_validator` for rejected-note requirement.
- **Tests**: 33 new tests in `tests/test_ontology_draft_review.py` covering single accept/reject, permissions, invalid input, status transitions (409 audit), metadata preservation, status filters, batch atomic semantics, and mixed generated+manual draft review.
- **Verification**: 365 passed (4 pre-existing Playwright E2E failures), 125 related tests pass, ruff clean, git diff clean. No new migration.
- **Boundaries**: No UI, no publish, no production Ontology write, no Agent review, no external KB modification, no DELETE/reopen/PATCH, no new migration, no 11.5/11.6.

**Next**: Phase 11.6 Agent-facing boundary review. Backend checkpoint (11.1–11.4) passed 2026-06-19 — 84 related tests, ruff clean, all 10 audit gates verified. Phase 11.5 UI is **deferred** to Kimi unified frontend refactor; CC does no frontend work. After 11.6 → Phase 12 planning.

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

### Real DeepSeek Agent Smoke — Phase 8.1 (2026-06-18)

**Status**: Delivered.

- **`scripts/smoke_agent_deepseek.py`**: Executed with `deepseek-v4-flash` via `https://api.deepseek.com`
- **Results**: S1 (finalize) ✅, S2 (call_tool `list_documents`) ✅, S3 (bad-key ChatError) ✅ — All smoke tests PASSED
- **No API key stored**: Real key only present in shell env during run; never committed
- **Verification**: Real `agent_decide()` returns valid `AgentDecision` JSON; tool_name/tool_arguments validation passes; ChatError correctly raised on auth failure

**Phase 8 complete**. All 8.1–8.5 delivered. Next: Phase 9 Ontology Core v1 — start with KB governance input (schema/frontmatter validation, entity extraction, wikilink relations, broken-link detection) before graph UI or modeling studio.

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

### Ontology Governance Read Model — Phase 9.1 + 9.2 (2026-06-18)

**Status**: Delivered.

- **New models**: `OntologyEntity` (`ontology_entities`) and `OntologyValidationIssue` (`ontology_validation_issues`) with group-scoped indices
- **Migration**: `0012_v12_ontology_read_model.py` — creates both tables, SQLite/PostgreSQL compatible
- **Service**: `src/semantic_lighthouse/services/ontology.py` — `scan_group()` validates all `ready` documents in a group:
  - Validates `entityType` (9 types) and `documentType` (6 types) against schema.md controlled vocabularies (hardcoded)
  - Detects: type_conflict, missing_entity_type, invalid_entity_type, invalid_document_type, missing_required_field (tags/created), invalid_controlled_value (status/source), invalid_list_field (tags/aliases)
  - Generates OntologyEntity records for valid entity documents; OntologyValidationIssue for all findings
  - Rebuild on each scan: clears and regenerates (idempotent)
- **API**: `POST /groups/{gid}/ontology/scan` (owner/admin), `GET /ontology/entities` (member+, filters: entity_type, status, q), `GET /ontology/issues` (member+, filters: severity, code)
- **Permissions**: scan = owner/admin only; read entities/issues = member+; all queries group-scoped
- **Tests**: 15 ontology tests (basic extraction, validation issues ×6, isolation, idempotency, entity fields, filtering ×2)
- **Full suite**: 224 passed, ruff clean, migration 0012 at head
- **Not in scope**: wikilink relations (9.3), governance issue list UI (9.4), ontology graph UI (9.5), Graph RAG, Agent writes to ontology, external KB modification

**Phase 9 complete**. Phase 10.1–10.5 delivered (governance operations complete). Phase 11/12 delivered (modeling drafts, quality gates, immutable packages). Phase 13 planning — see `docs/phase13-planning.md`.

### Real KB Curation Demo — Phase 10.2 (2026-06-18)

**Status**: Delivered.

- **Demo runner**: `scripts/run_ontology_curation_demo.py` — imports 74 docs, scans, deterministic triage, generates curation backlog
- **Triage**: 97 issues all confirmed — 90 unresolved_wikilink (classified by target_path: research/* → missing_research_doc_or_directory, KB_ENTITY_DIRS → missing_or_renamed_entity_doc, other → review_link_target), 7 stale_eval_gold_doc_id
- **Backlog**: 39 entries — 30 review_link_target, 7 update_eval_gold_doc_id, 2 create_missing_research_doc; priority: 20 high, 19 medium
- **Persistence**: rescan confirmed 97/97 triage preserved via stable issue_key
- **Report**: `docs/ontology-curation-demo-report.md`
- **Tests**: 35 unit tests for classify/priority/backlog helpers (`tests/test_ontology_curation_demo.py`)
- **Verification**: 76/76 tests (35 new + 41 ontology), ruff clean

### Ontology Graph UX Polish — Phase 10.3 (2026-06-18)

**Status**: Delivered.

- **Graph controls**: scope (selected/visible/all) + relation status (all/resolved/unresolved) dropdowns — frontend filtering, no new API
- **Legend**: entity_type color dots + resolved 实线 / unresolved 虚线
- **SVG tooltips**: `<title>` elements on nodes (title + type + status + path) and edges (source → target, status, label)
- **Selected node highlight**: larger radius, thicker stroke, bolder label
- **Unresolved targets list**: amber box below graph showing deduplicated unresolved target_paths — no fake nodes
- **Entity detail**: resolved relations are clickable to navigate to target entity; `open` attribute on `<details>` for better scannability
- **Issue filters**: triage_status dropdown (all/pending/confirmed/ignored) + code dropdown; ignored items visually weakened (opacity 0.45)
- **Mobile layout**: graph controls + legend + issue filters collapse vertically at 760px
- **Empty state**: clear empty message instead of blank area when no graph data
- **Still read-only SVG**: no graph library, no Graph RAG, no modeling studio, no Agent auto-write
- **Verification**: JS syntax valid (node --check), ruff clean, git diff --check clean. UI smoke blocked by pre-existing auth timing issue (unrelated to ontology)

### Evidence-to-Ontology Bridge — Phase 10.4 (2026-06-18)

**Status**: Delivered.

- **`static/js/util/ontology-links.js`**: cached entity index with `byDocumentId` and `bySourcePath` Maps; `findEntityForCitation()` matches citations to entities; `clearOntologyEntityCache()` for scan refresh
- **answer-card.js**: `ontologyIndex` opt (default null, backward-compatible); each citation that matches an entity shows `🔗 <title>` pill linking to `#/groups/{gid}/ontology?entity_id={id}`
- **ask.js**: loads ontology index after RAG answer + in recent detail; passes to answerCard
- **rag.js**: loads ontology index after RAG answer; passes to answerCard
- **tasks.js**: loads ontology index when expanding rag_run source detail; passes to answerCard
- **ontology.js**: supports `?entity_id=<id>` deep link — auto-selects entity on load; graceful when entity missing
- **Still read-only bridge**: RAG retrieval algorithm unchanged; no Graph RAG; no entity editing; no Agent auto-write
- **Verification**: all JS valid (node --check), ruff clean, git diff --check clean

### Governance Issue Triage — Phase 10.1 (2026-06-18)

**Status**: Delivered.

- **New fields**: `issue_key` (stable key for scan persistence), `triage_status` (pending/confirmed/ignored), `triaged_by`, `triaged_at`, `triage_note`
- **Migration**: `0015_v15_ontology_issue_triage.py`
- **Triage persistence**: Before scan clears old issues, saves `issue_key → {triage_status, triaged_by, triaged_at, triage_note}`. After generating new issues, restores triage for matching keys.
- **API**: `POST /ontology/issues/{id}/triage` (owner/admin only), `GET /ontology/issues?triage_status=`
- **Frontend**: Triage badges + ✓/✕/↺ buttons in governance issue list (owner/admin only); member sees read-only badges
- **Tests**: 5 triage tests (new issue pending / owner triage / member 403 / filter / scan persistence)
- **Verification**: 41/41 ontology tests, ruff clean, migration 0015 at head

### Real KB Governance Demo — Phase 9 Wrap (2026-06-18)

**Status**: Executed with real F:\ontology-kb\knowledge-graph (74 docs).

| Metric | Count |
|--------|-------|
| Imported | 74 |
| Entities | 74 |
| Relations | 186 (96 resolved, 90 unresolved) |
| Issues | 97 (90 unresolved_wikilink, 7 stale_eval_gold_doc_id) |

**Key findings**: 90 unresolved wikilinks (mostly `research/*` missing); 7 stale eval gold IDs; no duplicate titles/aliases. External KB unmodified.
**Demo runner**: `scripts/run_ontology_governance_demo.py`. **Report**: `docs/ontology-governance-demo-report.md`.

### Ontology Graph Console — Phase 9.5 (2026-06-18)

**Status**: Delivered.

- **New page**: `static/js/pages/ontology.js` — `#/groups/:gid/ontology`
- **Navbar**: "Ontology" link added
- **Capabilities**:
  - Summary metrics: entity count, relation count, unresolved count, issue count
  - Entity list (left): filterable by entity_type, status, q (title/alias search); click to select
  - Graph view (center): SVG circular layout with color-coded nodes per entity_type; resolved=实线, unresolved=虚线; click nodes to navigate
  - Entity detail (right): title, type, status, source, aliases, tags, path; outbound/inbound relations with resolved/unresolved status and target entity titles; related validation issues
  - Governance issue list (bottom): grouped by severity (error/warning), clickable entity links
  - Scan button: visible to owner/admin only; POSTs /scan then refreshes
  - Member: read-only view (scan button hidden, ALL API calls are GET only)
- **UI smoke**: `verify_ui` check "Ontology page renders" PASS
- **Still read-only**: No graph editing, no entity writing, no relation writing, no modeling studio, no Graph RAG, no Agent auto-write
- **Verification**: 36/36 ontology tests, ruff clean, verify_ui 20/23

### Governance Issue List — Phase 9.4 (2026-06-18)

**Status**: Delivered.

- **New issue types** (all `warning` severity, surfaced via existing `GET /ontology/issues`):
  - `unresolved_wikilink` — each unresolved `OntologyRelation` generates one issue per source entity
  - `duplicate_title` — normalized title conflicts across entities in the same group
  - `duplicate_alias` — alias-alias and alias-title conflicts; self-alias matching own title excluded
  - `stale_eval_gold_doc_id` — eval JSON expect_relevant_doc_ids not found in imported ontology KB docs
  - `eval_gold_check_failed` — eval JSON file unreadable (fallback)
- **Schema change**: `ontology_validation_issues.document_id` now nullable (migration `0014`) to support eval-scoped issues without document linkage
- **Stale eval check**: only triggers when group has imported ontology-style docs (non-upload: prefix + KB_ROOT_DIRS); never edits the eval file
- **Duplicate normalization**: strip + casefold; ignores empty aliases; self-alias-title match excluded
- **Tests**: 8 new governance issue tests (unresolved_wikilink, duplicate_title, duplicate_alias, alias-title-conflict, self-alias-excluded, stale eval guard, idempotent, cross-group)
- **Full suite**: 245 passed, ruff clean, migration 0014 at head

### Wikilink Relation Extraction — Phase 9.3 (2026-06-18)

**Status**: Delivered.

- **New model**: `OntologyRelation` (`ontology_relations`) — source_entity_id, target_entity_id (nullable), target_path, target_label, relation_type (=wikilink), status (resolved/unresolved), evidence_document_id
- **Migration**: `0013_v13_ontology_relations.py`
- **Wikilink parser** in `services/ontology.py`:
  - Regex: `[[...]]` with alias (`|`), anchor (`#`/`^`), relative path (`./`, `../`) support
  - Path normalization: forward slashes, `.md` suffix, traversal guard
  - Target resolution against group entity `source_path` (stripping `upload:` prefix)
  - Dedup by (source_entity_id, target_path, target_label)
- **API**: `GET /ontology/relations` (member+, filters: status, source_entity_id, target_entity_id, relation_type)
- **Scan rebuild**: clear order = issues → relations → entities; relation_count in scan response
- **Tests**: 10 relation tests (resolved, unresolved, alias, anchor, relative, member access, idempotent, cross-group, status filter, invalid entity)
- **Full suite**: 234 passed, ruff clean, migration 0013 at head

## Phase 9 Checkpoint Review (2026-06-18)

**Conclusion**: Phase 9.1–9.3 are on track. One bug found and fixed. Three test gaps filled.

### Findings

| Severity | Issue | Action |
|----------|-------|--------|
| **MEDIUM** | `![[image.png]]` embeds incorrectly parsed as wikilinks — the regex `[[...]]` matched `![[...]]` embeds, generating spurious relations | ✅ Fixed: regex changed to `(?<!!)\[\[([^\[\]]+?)\]\]` with negative lookbehind |
| LOW | No test for `[[target^block]]` caret anchor stripping | ✅ Added `test_caret_anchor_stripped` |
| LOW | No test for `![[embed]]` exclusion | ✅ Added `test_embed_exclamation_not_treated_as_wikilink` |
| LOW | No test for `relation_type` and `source_entity_id` filters | ✅ Added `test_relation_type_and_source_filter` |

### Verified Boundaries

- **Data model**: 3 tables (entities, issues, relations) — SQLite/PostgreSQL compatible. FK order correct. Downgrade safe when reversed (0013→0012). Unique constraints prevent duplicates.
- **Group isolation**: All queries scoped by `group_id`. Scan rebuild only clears current group. Cross-group tests pass.
- **Permissions**: scan = owner/admin only; entities/issues/relations = member+ readable. All 403 for non-members.
- **Scan rebuild**: Delete order = issues → relations → entities (no FK violation). Idempotent (28 tests confirm).
- **Wikilink parser**: `[[target]]`, `[[target\|label]]`, `[[target#anchor]]`, `[[target^block]]`, relative paths, `![[exclude]]`. `upload:` prefix stripped for resolution. Traversal guard prevents `../` escape.
- **Test coverage**: 28 ontology tests (15 entities + 13 relations). Full suite 237 passed.
- **No Graph RAG / modeling studio / Agent writes**: All read-only governance.

### Known Remaining (for 9.4)

- Unresolved relations are candidates, not governance issues yet
- Broken-link detection, duplicate title/alias detection, stale eval gold ID detection still pending
- `_normalize_path` function handles `upload:` prefix removal in index but doesn't test `import-local` paths directly

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

## Phase 10.5 Review Checkpoint (2026-06-18)

**Conclusion**: Phase 10 complete. All 10.1–10.4 deliverables verified end-to-end. No blocking issues. 6 stale documentation references found and fixed.

### Governance Pipeline Verified

- **Scan → Issues**: 74 docs → 74 entities, 186 relations, 97 issues (90 unresolved_wikilink, 7 stale_eval_gold_doc_id)
- **Triage → Persistence**: 97 confirmed via deterministic rules, rescan preserves all triage via stable issue_key
- **Curation Backlog**: 39 entries (30 review_link_target, 7 update_eval_gold_doc_id, 2 create_missing_research_doc)
- **External KB**: NOT modified — all read-only governance

### Evidence Bridge Verified

- **answerCard**: receives `ontologyIndex` via opts only (no internal API call)
- **ask.js / rag.js / tasks.js**: all load and pass `ontologyIndex`
- **ontology-links.js**: cached byDocumentId + bySourcePath index, `upload:` prefix stripped
- **Ontology deep link**: `?entity_id=nonexistent` handled gracefully (page renders, no crash)
- **Read-only bridge**: citations → entity badges are navigational only, no retrieval change

### Graph UX Verified

- Graph scope/status controls, legend, SVG tooltips, unresolved targets list
- Entity detail clickable relations, issue triage/code filters, mobile layout
- All filtering frontend-only, zero API changes, no graph library

### Documentation Fixes

| Severity | Issue | Action |
|----------|-------|--------|
| LOW | Roadmap header: "10.3–10.5 pending" — stale after 10.3–10.4 delivered | Fixed: "10.1–10.4 delivered; 10.5 review complete" |
| LOW | Roadmap Phase 10 header: "IN PROGRESS (10.1–10.2)" — stale | Fixed: "COMPLETE (10.1–10.4 delivered, 10.5 review passed)" |
| LOW | Roadmap 10.5 row: no checkmark | Fixed: ✅ with verification summary |
| LOW | PRD section 4: "Phase 8 Experience Integration" — extremely stale | Fixed: "Phase 10 Governance Operations (delivered)" |
| LOW | PRD section 5: "Phase 10 is planned" — stale | Fixed: "Phase 10 is delivered" |
| LOW | phase10-planning: 10.5 row no review result | Fixed: ✅ with review summary |
| LOW | phase10-planning status: "10.5 pending" | Fixed: "10.5 review complete ✅" |

### Verification

- **76 tests** (41 ontology + 35 curation demo) — all passed
- **ruff clean** across src, tests, scripts
- **git diff --check** clean
- **verify_ui**: 24 checks (21 PASS + 3 known-fragile — none ontology-related)

### Product Boundary Check

- ✅ No Graph RAG, no graph DB, no modeling studio
- ✅ No Agent auto-write to ontology entities/relations
- ✅ External KB not modified by any Phase 10 artifact
- ✅ All ontology read models group-scoped, permission-aware
- ✅ Evidence bridge is read-only navigation, not retrieval change
- ✅ Curation backlog is human action guidance only

**Next**: Phase 14.2 Dataset Asset. See `docs/phase14-planning.md`.

### Phase 14.1 — Business Pilot Project Foundation (2026-06-19)

**Status**: Delivered.

- **New model**: `BusinessProject` (`business_projects`) — id, group_id, name (≤160), business_goal (≤2000), entry_mode (problem_first/data_first), industry_template (≤80, nullable), stage (goal→pilot, backend-controlled, default goal), status (active/archived, default active), created_by, created_at, updated_at.
- **Migration**: `0018_v18_business_pilot_projects.py` — down_revision `0017_v17_ontology_model_packages`. SQLite/PostgreSQL compatible.
- **API**: `POST /groups/{gid}/projects` (owner/admin create), `GET /groups/{gid}/projects` (member+ list with status filter, limit/offset), `GET /groups/{gid}/projects/{pid}` (member+ detail), `PATCH /groups/{gid}/projects/{pid}` (owner/admin update name/business_goal/entry_mode/industry_template only), `POST /groups/{gid}/projects/{pid}/archive` (owner/admin, idempotent).
- **Permissions**: Member read, owner/admin write/archive. Outsider 403. Cross-group project 404 (no existence leak). Archived projects still readable.
- **Stage helper**: `services/projects.py` — `next_stage()` and `advance_stage()`. Sequential advancement only (goal→data→model→validate→pilot). Rejects skip, reverse, same, and unknown. No public advance API in 14.1.
- **Tests**: 57 tests in `tests/test_projects.py` covering create/read/update/list/archive permissions, cross-group isolation, field validation, archive idempotency, status filter, data isolation, and stage helper (15 unit tests).
- **Verification**: 57 passed, ruff clean, migration 0018 at head, git diff --check clean.
- **Boundaries**: No DatasetAsset, no data upload/profiling, no model bridging, no Object Runtime, no frontend, no delete/recover. Old features (RAG, Agent, Ontology drafts, tasks, conversations) not removed — they remain parallel capabilities.

### Phase 14.2 — Project Dataset Assets & Profiling (2026-06-19)

**Status**: Delivered.

- **New model**: `DatasetAsset` (`dataset_assets`) — id, group_id, project_id, original_name, storage_path, file_format (csv/xlsx), file_size, content_hash, status (ready/failed/archived), row_count, column_count, profile_json, created_by, timestamps. Unique constraint on (project_id, content_hash) for dedup.
- **Migration**: `0019_v19_dataset_assets.py` — down_revision `0018_v18_business_pilot_projects`. SQLite/PostgreSQL compatible.
- **API**: `POST /groups/{gid}/projects/{pid}/datasets` (owner/admin multipart upload), `GET` list with status filter/limit/offset, `GET /{dataset_id}` detail, `POST /{dataset_id}/archive` (idempotent). Member read, owner/admin upload/archive. Outsider 403, cross-group/project 404. Archived projects reject upload (409). Deduplication by content hash returns `deduplicated: true` with existing asset.
- **Profiling service**: `services/dataset_profiling.py` — CSV (stdlib csv, UTF-8/UTF-8-SIG, quoted fields) + XLSX (openpyxl read_only/data_only, first visible sheet). Column type inference (integer/number/boolean/date/datetime/string), null/distinct stats, PK candidate detection, within-project FK suggestion. Row scan cap 10k, distinct cap 1k, file size cap 50 MiB (reuses `max_document_upload_bytes`).
- **Privacy**: Sample values opt-in via `include_sample_values: bool` form field (default false). Capped at 3 per column. PII masked: email (te***@domain), phone (138****5678), ID card (110***********34).
- **Storage**: Files stored in `dataset-storage/{group_id}/{project_id}/{dataset_id}/{safe_name}`. Paths sanitized, traversal prevented. Temp-file → hash → profile → atomic rename. Failed profiles clean up temp file, no DB record. `dataset-storage/` added to `.gitignore`.
- **Stage advancement**: First ready DatasetAsset in a project at stage=goal → `advance_stage("goal", "data")` via existing helper. Duplicate/second upload does not re-advance.
- **Dependencies**: Added `openpyxl>=3.1.0` to `requirements.txt`. New config keys: `dataset_storage_path`, `dataset_max_scan_rows` (10k), `dataset_max_distinct_values` (1k).
- **Tests**: 53 tests in `tests/test_dataset_assets.py` covering unit (PII masking, type inference, CSV/XLSX profiling, PK/FK detection, content hash) and integration (upload CRUD, permissions, dedup, cross-project isolation, stage advancement, archive idempotency, XLSX upload, status filter, profile structure validation, error cleanup).
- **Verification**: 110 total (57 projects + 53 datasets) passed, ruff clean, migration 0019 at head, git diff --check clean.
- **Boundaries**: No LLM model suggestions, no Ontology draft/relation creation from profiles, no Object Runtime, no .xls support, no frontend, no delete/recover. Old features preserved.

### Phase 14.3 — Data-to-Model Bridge (2026-06-19)

**Status**: Delivered.

- **Migration**: `0020` — nullable `project_id` + `source_dataset_id` FKs on `ontology_modeling_drafts`. Batch mode. Legacy compatible.
- **API**: `POST /groups/{gid}/projects/{pid}/model-drafts/generate` — owner/admin, deterministic, idempotent. goal→409, archived→409, no ready datasets→400. data→model on success.
- **Service**: `dataset_modeling.py` — Object Types (snake_case api_name, best PK per confidence/position), Properties (one per column, type-mapped, required=not nullable), Link Types (from FK suggestions, many_to_one). No Action Types. Generation key = `project_id:dataset_id:draft_type:business_key`. Evidence excludes sample values + storage_path.
- **Review chain**: Existing review endpoints work on dataset drafts unchanged.
- **Tests**: 27 tests. 125 combined (26 drafts + 34 review + 38 contract + 27 modeling) — zero regressions.
- **Verification**: Migration upgrade/downgrade verified. 125 combined passed. Ruff clean.

## Agent Instructions For The Next Session

Start by reading `AGENTS.md`, `PRODUCT.md`, `docs/product-alignment-prd.md`, `CLAUDE.md`, this handoff, and the latest engineering memory files. Then run review and tests according to `docs/development-workflow.md` before changing code.

Do not frame the project as only a RAG/Agent portfolio. The current product direction is the Ontology semantic operating layer. Phase 14 is underway — 14.1–14.3 delivered; 14.4 Model Validation Gate is next. Old RAG/Agent/Ontology features remain available as parallel capabilities but the product main chain is now the business pilot five-stage pipeline.

### Backend Review A (2026-06-19) — Complete

**Findings fixed**:

| Severity | Issue | Fix |
|----------|-------|-----|
| HIGH | File upload `read()` unbounded before size check — OOM risk | `read(max_bytes + 1)` prevents unbounded allocation |
| HIGH | Archive didn't update `updated_at` in both projects and datasets | `updated_at = utc_now()` before commit |
| MEDIUM | Duplicate upload race: IntegrityError orphaned permanent file | Catch `IntegrityError`, clean up file, return existing |
| MEDIUM | Dead code: `_safe_name`, `FKMatch` dataclass unused | Removed |
| MEDIUM | `file.file.seek(0)` no-op after full read | Removed (redundant with `read(N)` approach) |
| MEDIUM | `BusinessProjectUpdateRequest` lacked name trim validator | Added `@field_validator("name")` for `None`-safe trim |
| MEDIUM | `openpyxl` missing from `pyproject.toml` | Added to dependencies |
| LOW | Documentation drift: stale status lines | Fixed all: planning v2, handoff header + footer, roadmap |

**Residual risks (accepted, not blocking)**:
- Concurrent upload race for different content with same filename: temp file naming uses `uuid4().hex` prefix — collision probability negligible.
- Double file read (upload stream → disk, disk → profiling) — same pattern as document upload path; acceptable for 50 MiB cap.
- No latency/cost tracking for profiling — profiling is pure Python, no LLM; negligible.

**Frontend**: moratorium lifted 2026-06-19 for Frontend Refactor F1 (Swiss app shell F1A delivered, Ontology workspace F1B pending).

**MCP moratorium**: do not implement MCP runtime during Phase 14. Do not add an
MCP SDK/dependency or register MCP resources/tools. The read-only gateway is a
post-Phase-14 candidate only. Any future prompt must follow
`docs/mcp-agent-boundary-design.md`; no write capability is allowed without a
separate Safety Lane plan reusing backend authorization, audit, and HITL.

### Phase 14.5 — Pilot Read Runtime + Unified Query Contract (2026-06-20)

**Status**: Delivered. Phase 14 complete. All 14.1–14.5 delivered.

**What was built**:

- **New model**: `OntologyDatasetBinding` (`ontology_dataset_bindings`, migration `0022`). Fields: id, group_id, project_id, package_id, dataset_id, object_type_api_name, primary_key_column, property_mappings (JSON), status (active/stale), created_by, created_at, updated_at. Unique constraint on (package_id, object_type_api_name). Never stores sample_values, raw rows, or storage_path.

- **Binding generation**: `POST /runtime/bindings/generate` (owner/admin). Deterministically maps accepted business_v1 Object Type drafts (with source_dataset_id) to DatasetAssets. Property mappings from accepted Property drafts: property api_name → column name. PK column resolved through Object Type draft's primary_key property reference → matching Property draft's column evidence. Idempotent. Returns structured issues on unresolvable cases — never guesses, never calls LLM. Action Types never bound. Link Types not joined.

- **Binding read**: `GET /runtime/bindings` (member+). Returns active bindings for latest project package. Validates project existence (404 for non-existent/cross-group).

- **Unified query**: `POST /runtime/query` (member+). Restricted JSON request — no SQL, no DSL, no expressions. object_type, optional fields (bound property whitelist), optional equality filters, limit (default 20, max 100), offset (default 0, max 10000), explain_only. Uses latest project package + bindings. Only ready/non-archived datasets. CSV/XLSX via controlled parsing. File path resolved and validated within dataset_storage_path/group/project. Contract value_type conversion with explicit errors. Never returns storage_path, sample profile, internal stack traces, or unselected columns.

- **Explain/provenance**: Includes package id/version/semantic_hash, binding id, dataset id/content_hash, selected fields, filter field names, limit/offset. NEVER includes filter values, raw rows, file paths, or secrets.

- **Pilot activation**: `POST /runtime/activate` (owner/admin). Validates all dataset-grounded Object Types have bindings, datasets ready with ≥1 row, smoke query per binding. On full success, advances validate → pilot via existing stage helper. Idempotent. Ordinary query never advances stage.

- **Permissions**: member reads bindings/query; owner/admin generates/activates; outsider 403; cross-group/cross-project 404.

- **Path safety**: Resolved path validated within `dataset_storage_path/{gid}/{pid}/`. Traversal rejected.

- **Tests**: 56 tests in `tests/test_project_runtime.py`. All phases combined: 216 tests pass (56 + 57 projects + 53 datasets + 27 modeling + 23 validation). Zero regressions across Phase 14.

- **Verification**: Ruff clean, git diff --check clean, migration 0022 at Alembic head.

- **Hard boundaries enforced**: No MCP server/client/SDK, no custom query language, no SQL/DSL/AST, no Graph RAG, no relation joins, no Action execution, no data write-back, no new dependencies, no frontend changes, no full pytest run (only Phase 14 + related tests).

**Residual risks**: Bound dataset files can be moved/deleted on disk → query returns 422 (not silent). Concurrent binding generation for same package may produce IntegrityError — handled by unique constraint. No caching layer — repeated queries re-read files.

**Next**: Backend Review C / Phase 14 closeout. MCP remains post-Phase 14 candidate — see `docs/mcp-agent-boundary-design.md`.

### Backend Review C — Phase 14.5 Hardening (2026-06-20)

**Status**: Complete. Seven review items fixed across audit, filter semantics, type/privacy, binding strictness, compiled contract usage, activation gate, and code hygiene.

Key fixes: Added `OntologyRuntimeAudit` model + migration `0023`. Fixed filter/pagination order (filter-before-offset/limit). CSV streaming (no `read_bytes()`). Type-converted filter values. Error messages no longer leak raw cell values. PK resolution strict — no profile fallback. Property mappings cross-validated against compiled contract + draft evidence + dataset profile. `compile_business_contract()` is single source of truth for fields/value_types/semantic_hash. Activate smoke uses full `execute_query` path. IntegrityError handling on concurrent binding generation.

Verification: 79 runtime tests, 239 Phase 14 combined, 734 full non-E2E (0 failures). Ruff clean. Migration 0023 upgrade/downgrade verified.

**Residual risks**: Audit records are write-only (no query API exposed — by design). XLSX uses read_only (acceptable for ≤50 MiB). Contract re-compiled per query (acceptable overhead, caching deferred).

**Next**: Phase 14 COMPLETE. Future candidates only: MCP read-only gateway (post-Phase 14, requires dedicated Safety Lane plan), Evidence + Object dual-plane query, Domain Pack/Knowledge Artifact. NOT started.

### Frontend F2A — Guided Pilot Entry + Data Stage (2026-06-20)

**Status**: Delivered. Navigation restructured to Pilot-first. Project list + detail pages with goal/data stages.

**What was built**:
- Navbar restructured: Pilot (default), Ontology, 工作区, 更多工具 (dropdown with 问答/知识库/对话/任务/Agent).
- Pilot project list (`/groups/:gid/projects`): project cards with stage rail, create dialog, empty state.
- Pilot project detail (`/groups/:gid/projects/:pid`): five-stage progress rail, goal stage info + upload CTA, data stage dataset list/profile/upload.
- API improvements: FormData auto-detection, unified human-readable error messages.
- Design: Minimalism & Swiss Style via ui-ux-pro-max skill. Monochrome + gold accent.
- First-use paths: login → Pilot list, new workspace → Pilot empty state, group switch → Pilot list.
- Old routes preserved, all accessible via 更多工具 or direct URLs.

**Next**: Frontend F2B — Model → Validate → Pilot full operation loop.

Do not rely on chat history. Use `git log -1 --oneline` for the latest verified baseline and confirm a clean worktree. Frontend F2A delivered. F2B next.
