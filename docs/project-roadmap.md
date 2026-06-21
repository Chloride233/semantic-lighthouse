# Semantic Lighthouse — Project Roadmap

**Last updated**: 2026-06-20
**Current phase**: See `docs/project-status.toml` — canonical project state.

---

## Current Baseline

| Layer | Capability | Status |
|-------|-----------|--------|
| V1 | JWT auth, BCrypt, refresh rotation, group roles, group_id isolation | Stable |
| V2 | Markdown ingestion, single upload, keyword search, citation metadata | Stable |
| V2.1 | Aliyun embedding, pgvector, semantic search, fake provider | Stable |
| V2.2 | MD/TXT/PDF/DOCX chunked upload, resumable sessions, instant dedup | Stable (cleanup hardened) |
| V3 | DeepSeek RAG answer, confidence, knowledge gaps, evidence gate | Stable |
| V3.3 | RAG run audit persistence, group-scoped replay | Stable |
| V3.4 | Async ETL pipeline, structure-aware chunking, ingestion jobs, HNSW | Stable (hardened) |

**Metrics**: 749 non-E2E pytest passed, ruff clean, alembic `0023` at head (2026-06-20). Production safety checks delivered (APP_ENV, JWT/cookie/database validation).

---

## Product Alignment: Ontology Semantic Operating Layer ← UPDATED (2026-06-18)

**Goal**: Keep the project centered on the path from trusted evidence and user-confirmed action toward an enterprise Ontology semantic operating layer.

Ontology in this project means business objects, properties, relationships, actions, permissions, evidence, and Agent-facing interfaces. It is not just a database schema, not just a knowledge graph, and not just a RAG document library.

Phases 8–10 delivered the foundation:

```text
RAG answer -> user-confirmed task -> Agent/HITL -> audit trail (Phase 8)
schema/frontmatter validation -> entity extraction -> wikilink relation extraction -> broken-link detection -> ontology graph/entity detail (Phase 9)
governance issue triage -> curation demo -> graph UX polish -> evidence bridge -> review (Phase 10)
```

Phase 11 delivered human-reviewed Ontology Modeling Drafts v1. Phase 12 delivered quality-gated, immutable model contract packages. Accepted packages remain internal snapshots, not production Ontology publication.

| # | Task | Acceptance |
|---|------|------------|
| A.1 | Product boundary PRD | ✅ `docs/product-alignment-prd.md` explains Ontology semantic operating layer, Phase 8, Phase 9, Agent boundaries, and out-of-scope items |
| A.2 | Entry-file alignment | ✅ `AGENTS.md`, `CLAUDE.md`, `PRODUCT.md`, `README.md`, roadmap, and handoff point to the same Ontology direction |
| A.3 | Next-step task design | ✅ Task board v1.1 delivered: confirm button, status=cancelled, source RAG run inline detail, task filters, 20 tests |
| A.4 | Web search status | ✅ Web search remains Discovery until low-confidence question validation proves value |
| A.5 | Ontology Core v1 sequence | ✅ Phase 9 starts with governance and graph visibility before modeling studio, Graph RAG, or Agent ontology writes |

**Acceptance**: A new session should not describe Semantic Lighthouse as only a RAG/Agent project. It should describe the current product as a trusted evidence/action foundation for an Ontology semantic operating layer.

---

## Phase 0: Engineering Baseline Stabilization ← DELIVERED (2026-06-16)

**Goal**: Confirm every deliverable from V1–V3.4 is verifiable, clean, and deployable.

| # | Task | Acceptance |
|---|------|------------|
| 0.1 | Full test suite pass (pytest + ruff + Alembic) | 55 passed, ruff clean, migration at head |
| 0.2 | PostgreSQL + pgvector real smoke | Register → upload → ETL → semantic search → RAG answer on real pgvector |
| 0.3 | .gitignore audit — no secrets, no artifacts, no runtime data | `git check-ignore` on `.env*`, `*.db`, `.tmp/`, `.venv/`, `.claude/` |
| 0.4 | Cloud smoke playbook verified or documented as pending | `docs/cloud-smoke-playbook.md` reviewed |
| 0.5 | Dependency manifest clean | `requirements.txt` + `requirements-dev.txt` install without errors |
| 0.6 | Document known limitations | PDF OCR, DOCX tables, read_bytes memory, SQLite vs pgvector gap |

**Acceptance**: All 0.1–0.6 gates green. Phase 0 complete when real pgvector smoke is run (local Docker or cloud ECS).

---

## Phase 1: Retrieval Quality Engineering ← FOUNDATION EXISTS

**Status**: hybrid search and eval harness have a working foundation. Not starting from zero.

**Goal**: The system can measure and improve what it retrieves.

| # | Task | Acceptance |
|---|------|------------|
| 1.1 | Hybrid search (keyword + vector fusion) | ✅ Foundation exists; remaining: configurable weights, measurable recall improvement |
| 1.2 | Rerank pass on retrieval results | Rerank model or cross-encoder, latency budget documented |
| 1.3 | Retrieval evaluation harness | ✅ Foundation exists (`scripts/run_eval.py`, `check_eval_thresholds.py`, 24 ontology queries); remaining: gold-standard Q&A pairs, recall@k, MRR, NDCG |
| 1.4 | Chunk overlap and context window tuning | Evidence that overlap improves retrieval on real documents |
| 1.5 | Embedding model comparison | Measured quality difference, cost/latency tradeoff |

**Acceptance**: `docs/retrieval-eval-report.md` with before/after metrics for at least 10 gold questions.

---

## Phase 2: Knowledge Governance & Document Lifecycle ← PARTIALLY DELIVERED

**Status**: Knowledge Governance v1 delivered (2026-06-17). Remaining items are v2 enhancements.

| # | Task | Acceptance |
|---|------|------------|
| 2.1 | Document metadata schema (entity type, status, source, tags) | ✅ Frontmatter validation, metadata badges in UI, search/filter by entityType/source/ontology status |
| 2.2 | Document deprecation and archival | ✅ `status=archived` excludes from search, `archived_by`/`archived_at`/`archive_reason` audit fields (migration `0011`), `GET /documents?status=` server-side filter |
| 2.3 | Group-level knowledge graph view | Entities and relations from ingested docs |
| 2.4 | DOCX table/header/footer extraction | Table content appears in chunks with structure preserved |
| 2.5 | Bulk import with progress tracking | `POST /import-local` returns job ID, async progress queryable |

**Acceptance**: Archive audit + status filter + metadata display delivered. Next: versioning, bulk governance, KG view.

---

## Phase 3: RAG Answer Quality Hardening

**Goal**: Answers are grounded, auditable, and the system knows when it doesn't know.

| # | Task | Acceptance |
|---|------|------------|
| 3.1 | Citation precision scoring | Each citation has a relevance score; low-score citations flagged |
| 3.2 | Answer-vs-context factual consistency check | Second LLM pass or heuristic check |
| 3.3 | "I don't know" threshold tuning | Configurable confidence floor; below threshold → no answer |
| 3.4 | Multi-document RAG (cross-document synthesis) | Answer draws from ≥2 documents when question spans topics |
| 3.5 | RAG answer comparison (A/B eval) | Side-by-side comparison of two retrieval strategies |

**Acceptance**: `docs/rag-quality-report.md` with 20-question eval set, confidence distribution, citation accuracy.

---

## Phase 4: V4 Agent Multi-Turn Dialogue ← PARTIALLY DELIVERED

**Status**: Conversation session + frontend exist. Remaining items are UX hardening.

| # | Task | Acceptance |
|---|------|------------|
| 4.1 | Conversation session management | ✅ `POST /conversations`, `POST /conversations/{id}/messages`, group-scoped, frontend console |
| 4.2 | Multi-turn context window management | Sliding window or summarization; token budget enforced |
| 4.3 | Tool-use: search within conversation | Agent can call keyword/semantic search as a tool |
| 4.4 | Agent memory across sessions | User preferences, past questions, cited documents remembered |
| 4.5 | Agent audit trail | Every tool call, retrieved chunk, and generated response logged |

**Acceptance**: Conversations API + frontend delivered (Phase 4.1). Conversation UX hardening delivered (Phase 8.4: citations, tool calls, failure states, context indicators). Next: context window management, source traceability.

---

## Phase 5: Cloud Deployment & Operations

**Goal**: The system can be deployed, monitored, and debugged in production.

| # | Task | Acceptance |
|---|------|------------|
| 5.1 | Health check and metrics endpoint | `/health` returns DB, embedding, chat provider status |
| 5.2 | Structured logging (JSON) | Log levels configurable, request IDs for tracing |
| 5.3 | Docker Compose production guide | One-command deploy on Ubuntu 24.04 |
| 5.4 | Database backup and restore playbook | `pg_dump` / `pg_restore` documented and tested |
| 5.5 | HTTPS + domain + Nginx reverse proxy | Swagger at `https://domain/docs`, auto-renew TLS |

**Acceptance**: `docs/production-runbook.md` with deploy, backup, restore, and troubleshoot sections.

---

## Phase 6: Frontend Engineering Console ← DELIVERED (2026-06-12)

**Status**: Delivered. Vanilla JS ES modules + hash router, zero npm, 6 pages. Playwright E2E tests (6.5) not done.
**Goal**: Build a real, maintainable frontend console after the backend/RAG chain is stable.

| # | Task | Acceptance |
|---|------|------------|
| 6.1 | Operator console information architecture | Auth, groups, documents, ingestion jobs, retrieval eval, RAG runs are navigable |
| 6.2 | Document and ingestion management UI | Upload, progress, retry, archive, failure reason visible without Swagger |
| 6.3 | Retrieval and RAG evaluation UI | Query, citations, scores, confidence, knowledge gaps shown clearly |
| 6.4 | Permission-aware UI states | Owner/Admin/Member see only allowed actions |
| 6.5 | Frontend smoke and regression checks | Key flows verified by browser tests |

**Acceptance**: A reviewer can complete the core demo from the browser without using Swagger.

---

## Phase 7: Advanced Agent Orchestration ← DELIVERED (backend)

**Status**: 7.1–7.5 delivered. V2.1 LLM tool loop (`78c3d9a`); V2.2 provider + audit hardening (`ca58506`); V2.3 fake-provider eval delivered + real smoke executed and passed (`fd68060`, `scripts/smoke_agent_deepseek.py`). Agent audit hardening delivered (`a761afc`). 39 agent tests + 6 audit tests + 6 config tests. No LangGraph runtime.

**Current gap**: Agent backend is complete. Agent console page (Phase 8.2) delivered. Remaining gap: real DeepSeek smoke recording (Phase 8.1).

| # | Task | Acceptance |
|---|------|------------|
| 7.1 | Agent tool registry and permission policy | ✅ 3 tools, role-gated, unit tested |
| 7.2 | Workflow planning with explicit state | ✅ 4-state FSM, step audit records |
| 7.3 | Long-term memory governance | ✅ KV store with scope/ttl/source |
| 7.4 | Human-in-the-loop checkpoints | ✅ risky → awaiting_confirmation |
| 7.5 | Agent evaluation set | ✅ 39 tests, 5 fake-provider scenarios, 6 audit tests, 6 config tests |

**Acceptance**: 39 agent tests pass. Backend delivered. Next: frontend visibility, real smoke recording, V2.4 scope.

---

## Phase 8: Experience Integration ← DELIVERED

**Goal**: Make existing backend capabilities visible, usable, and demonstrable. No new backend Agent features. Focus on frontend visibility, UX hardening, demo scripts, and task source traceability expansion so the current loop can be shown before Phase 9.

| # | Task | Acceptance |
|---|------|------------|
| 8.1 | Real DeepSeek Agent smoke recording | ✅ `scripts/smoke_agent_deepseek.py` executed with `deepseek-v4-flash`, S1/S2/S3 all PASSED (2026-06-18) |
| 8.2 | Agent run/step/HITL frontend page | ✅ Agent console page with run lifecycle, step timeline, and HITL confirm/reject/stop (2026-06-18); `verify_ui` smoke coverage |
| 8.3 | Task source_type expansion | ✅ `conversation`, `agent_run`, `manual` source types alongside existing `rag_run` (2026-06-18) |
| 8.4 | Conversation UX hardening | ✅ Visible citations, knowledge gaps, context indicators, tool details, send/error states (2026-06-18) |
| 8.5 | Demo scenario scripts | ✅ `docs/interview-demo-questions.md` refreshed with Ontology-oriented Phase 8 full-loop demo script (2026-06-18) |

**Acceptance**: ✅ Phase 8 demonstrable complete. Full loop — RAG answer → task creation → Agent tool execution → HITL → audit trail — visible from the frontend. Real DeepSeek smoke passed.

---

## Phase 9: Ontology Core v1 - Governance & Graph ← DELIVERED

**Goal**: Turn the existing ontology KB seed corpus into governed, group-scoped ontology entities, relationships, validation issues, and graph/detail views. This is the first product step from trusted RAG toward the semantic operating layer.

| # | Task | Acceptance |
|---|------|------------|
| 9.1 | Schema/frontmatter validation | ✅ Detect missing required fields, invalid `entityType`/`documentType`, invalid status/source values, and entity/document type conflicts (2026-06-18) |
| 9.2 | Entity extraction read model | ✅ Imported documents produce group-scoped ontology entity records with title, aliases, entity_type, source_path, source, status, tags, and document_id (2026-06-18) |
| 9.3 | Wikilink relation extraction | ✅ Wikilinks parsed into `ontology_relations` with resolved/unresolved status, target_label, relative-path resolution, anchor stripping, idempotent rebuild (2026-06-18) |
| 9.4 | Governance issue list | ✅ Unresolved wikilinks, duplicate titles/aliases, stale eval gold IDs surfaced as `OntologyValidationIssue` records; `document_id` made nullable for eval-scoped issues (2026-06-18) |
| 9.5 | Ontology graph and entity detail UI | ✅ Console page with entity list (filterable), SVG graph (read-only), entity detail panel (relations + issues), governance issue list, scan button for owner/admin (2026-06-18) |

**Known first governance inputs**:

- `F:\ontology-kb\knowledge-graph` references `research/...` in `INDEX.md` / `AUTO_INDEX.md`, while the inspected workspace lacks a `research/` directory.
- `docs/eval/rag-queries-ontology.json` includes expected document IDs that do not exist in the current KB, such as `concepts/agent`, `concepts/ontology-sdk`, `vendors/palantir-foundry`, `vendors/huawei-fusioninsight`, `cases/banking-knowledge-graph-customer-360`, and `cases/healthcare-ontology-patient-modeling`.
- Handoff previously referenced missing `docs/kgov-v1-report.md`; this is now treated as a documentation drift issue, not a delivered artifact.

**Out of scope for Phase 9**:

- full Object Type / Property / Link Type / Action Type modeling studio
- Graph RAG
- Agent auto-writing ontology entities, relations, or actions
- automatic edits to the external KB


## Phase 10: Governance Operations & Demo Polish ← COMPLETE (10.1–10.4 delivered, 10.5 review passed)

**Goal**: Operationalize governance findings, polish the demo loop, and build the evidence-to-ontology bridge before Graph RAG or modeling studio. See `docs/phase10-planning.md`.

| # | Task | Description |
|---|------|-------------|
| 10.1 | Governance issue triage design | ✅ `triage_status` (pending/confirmed/ignored), `POST /issues/{id}/triage`, stable `issue_key` for scan persistence, frontend triage controls for owner/admin (2026-06-18) |
| 10.2 | Real KB curation demo script | ✅ `scripts/run_ontology_curation_demo.py` — deterministic triage, 97 confirmed, 39 backlog entries, rescan persistence verified (2026-06-18) |
| 10.3 | Ontology graph UX polish | ✅ Graph scope/status controls, legend, SVG tooltips, unresolved targets list, entity detail clickable relations, issue triage/code filters, mobile layout — still read-only SVG, no graph library (2026-06-18) |
| 10.4 | Evidence-to-ontology bridge | ✅ `ontology-links.js` entity index, citation→entity badges in answerCard, ask/rag/tasks pages pass ontologyIndex, ontology deep link `?entity_id=` — read-only bridge, not Graph RAG (2026-06-18) |
| 10.5 | Phase 10 review | ✅ End-to-end governance pipeline verified: 76 tests pass, ruff clean, demo reproducible, evidence bridge functional, docs sync complete (2026-06-18) |

**Out of scope**: Graph RAG, modeling studio, Agent auto-write, external KB auto-fix, graph database migration.


## Phase 11: Ontology Modeling Drafts v1 ← BACKEND COMPLETE (11.1–11.4+11.6 delivered, 11.5 UI deferred)

**Goal**: Turn the governed entity/relation/issue read model into human-reviewable Object Type, Property, Link Type, and Action Type drafts — without Graph RAG, a full modeling studio, or Agent auto-write. See `docs/phase11-planning.md`.

| # | Task | Description |
|---|------|-------------|
| 11.1 | Modeling draft boundary + schema | ✅ `OntologyModelingDraft` model, migration `0016`, `object_type`/`property`/`link_type`/`action_type`, status lifecycle (proposed/accepted/rejected), evidence linkage FKs (2026-06-19) |
| 11.2 | Draft read model / API | ✅ `POST /groups/{gid}/ontology/drafts` (owner/admin), `GET /groups/{gid}/ontology/drafts` (member+) with draft_type/status/q/source_entity_id filters, group-scoped evidence validation (2026-06-19). Review hardened: rescan evidence lifecycle relink, evidence_refs boundary (2026-06-19). |
| 11.3 | Draft generation | ✅ Deterministic rules from existing entities/relations, no LLM |
| 11.4 | Human review workflow | ✅ proposed → accepted/rejected, reviewer audit, single + batch API, atomic semantics, status transition rules, 33 tests (2026-06-19) |
| 11.5 | UI modeling panel | **Deferred** — entity detail panel + draft list deferred. F2B delivered model/validate/pilot UI through the Pilot project workspace instead. |
| 11.6 | Agent/MCP Boundary Design | ✅ Design-only boundary: existing Agent registry plus future MCP identity mapping, server-side group authorization, invocation audit, bounded/provenance-preserving output, and no-write gates. See `docs/ontology-agent-boundary.md` and `docs/mcp-agent-boundary-design.md`. No MCP runtime or dependency. |

**Out of scope**: Full modeling studio, Graph RAG, graph database, Agent auto-write, external KB auto-fix, draft-to-production pipeline. Phase 11.5 entity UI deferred — model/validate/pilot UI delivered through F2B Pilot workspace.

**Next**: Phase 13 is PLANNED — see `docs/phase13-planning.md`. Phase 12 is complete.


## Phase 12: Ontology Model Quality & Contract Packages v1 ← COMPLETE (12.1–12.6 delivered)

**Goal**: Turn Phase 11 accepted drafts into verified, quality-gated, immutable model contract packages — without treating accepted as production, without Graph RAG, without Agent auto-write. See `docs/phase12-planning.md`.

| # | Task | Description |
|---|------|-------------|
| 12.1 | Real KB modeling draft demo | ✅ 76 drafts (8 OT, 48 prop, 17 link, 3 action) from real KB. Technical integrity PASS. All hard checks 0, idempotent. Report: `docs/ontology-modeling-draft-demo-report.md` (2026-06-19) |
| 12.2 | Draft quality gates | ✅ Validator service + API. 9 error codes, 7 warning codes. Real validation: 0 errors, 53 warnings, WARN status. `GET /drafts/quality` (member+). 16 tests (2026-06-19) |
| 12.3 | Immutable model package read model | ✅ Migration 0017 + builder service. Accepted-only, quality gate, dependency gate, content hash, versioned, idempotent. 27 tests (2026-06-19) |
| 12.4 | Package read/export API | ✅ POST create + GET list/detail/export. Owner/admin create, member+ read. No PATCH/DELETE. 8 API tests (2026-06-19) |
| 12.5 | Action and permission contract | ✅ Package builder enforces action_contract (required_role, confirmation_requirement, evidence_requirement). Deterministic defaults + manual validation. 14 tests (2026-06-19) |
| 12.6 | Real demo and phase review | ✅ Real KB chain: 76 drafts → 5 explicitly reviewed drafts → WARN package; stable hash/idempotency and audit chain verified. 434 non-E2E tests passed (2026-06-19). |

**Completion**: Phase 12 turns accepted drafts into quality-gated, immutable, exportable contract snapshots with declarative Action permission requirements. It does not publish or execute an Ontology.

**Out of scope**: Full modeling studio, Graph RAG, graph database, Agent auto-write/auto-publish, external KB modification, production schema write, Phase 11.5 entity detail UI (deferred).


## Phase 13: Typed Business Ontology Contract & Manufacturing Pilot v1 ← **COMPLETE** (13.1–13.6 all delivered, 12/12 gates PASS)

**Goal**: Advance the Phase 12 audit-type model package into a deterministically validated, application-readable business Ontology contract with stable type definitions — without publishing to production, storing object instances, executing Actions, or generating an SDK. See `docs/phase13-planning.md`.

| # | Task | Description |
|---|------|-------------|
| 13.1 | Business contract profile specification | ✅ `docs/phase13-business-contract-spec.md` — profile identity, payload fields, controlled vocabularies, compiled manifest spec, validator error codes. Documentation-only, no tests. (2026-06-19) |
| 13.2 | Deterministic business contract validator | ✅ `validate_business_contract()` pure function — 22 error + 3 warning codes, 7 parametrized tests (38 total). No DB, no LLM, deterministic output order. (2026-06-19) |
| 13.3 | Business contract compiler | ✅ `compile_business_contract()` — field whitelist, deterministic sort, semantic_hash (sha256:), provenance block. Raises `BusinessContractCompilationError` on validator FAIL. 7 tests. (2026-06-19) |
| 13.4 | Read-only contract export API | ✅ `GET /packages/{pid}/contract` — member+ read, outsider 403, cross-group 404, 422 on validation failure. Reuses compiler directly. 8 API tests. (2026-06-19) |
| 13.5 | Manufacturing pilot v1 | ✅ Independent demo group, 11 business_v1 drafts (2 OT + 6 Prop + 2 Link + 1 Action). Full pipeline: draft create → batch review → package build → contract export → idempotent rebuild → cross-group isolation. PASS quality, semantic_hash stable. Demo script + 7 tests. (2026-06-19) |
| 13.6 | Phase 13 review | ✅ All 12 review gates PASS. 495 non-E2E tests, ruff clean. Minor fix: `parameters: None` double-reporting. Decision: Phase 13 COMPLETE. Frontend F1/F2 subsequently delivered by CC (Swiss app shell + Guided Pilot workspace). See `docs/phase13-review.md`. (2026-06-19) |

**Out of scope**: Frontend, modeling UI, business object instance tables, package activate/publish, Action execution, Functions runtime, OSDK/code generation, MCP/Agent tool registration, Graph RAG, ERP/MES/PLC integration, external KB modification, knowledge_meta→business_v1 auto-conversion, full JSON Schema/OpenAPI generation, generic manufacturing framework.


## Phase 14: Business Pilot Project ← Data → Model → Validate → Pilot ← **COMPLETE** (14.1–14.5 all delivered)

**Goal**: Shift the product from parallel features toward a guided five-stage business pilot main chain, ending with a deterministic, permission-isolated, explainable read runtime that proves the Ontology contract can read real business objects. See `docs/phase14-planning.md`.

| # | Task | Description |
|---|------|-------------|
| 14.1 | Business Pilot Project Foundation | ✅ `BusinessProject` model, migration `0018`, CRUD/archive API, permissions, stage helper. 57 tests. |
| 14.2 | Dataset Asset & Profiling | ✅ `DatasetAsset` model, migration `0019`, CSV/XLSX upload, metadata-first profiling, PK/FK suggestions, PII masking, stage advancement goal→data. 53 tests. |
| 14.3 | Data-to-Model Bridge | ✅ Migration `0020` (project_id + source_dataset_id on drafts), deterministic dataset→business_v1 draft generation (object/property/link types), evidence privacy, idempotency, stage advancement data→model, review chain reuse. 27 tests. |
| 14.4 | Model Validation Gate | ✅ Migration `0021` (scope_key + project_id on packages), project-scoped quality/package/contract API, WARN override audit, FAIL blocks absolutely, stage model→validate, legacy isolation. 23 tests. |
| 14.5 | Pilot Read Runtime + Unified Query Contract | ✅ Migration `0022` (OntologyDatasetBinding) + `0023` (OntologyRuntimeAudit), deterministic binding generation from accepted contract + dataset profiles, unified read-only query with typed filter conversion/streaming CSV/filter-before-offset-limit/compiled contract as truth, pilot activation with full smoke query, audit fail-closed, path safety, permissions, provenance sanitization. 94 runtime tests. No DSL, no MCP, no Graph RAG. |

**Next**: Product closeout/review — verify full chain, refresh demo scripts, confirm all docs aligned.

---

## Frontend F2: Guided Business Pilot Workspace ← F2A DELIVERED

| # | Task | Status |
|---|------|--------|
| F2A | Pilot entry, project creation, goal + data stage, nav restructure | ✅ Delivered |
| F2B | Model → Validate → Pilot full operation loop (drafts/review/quality/package/bindings/activate/query) | ✅ Delivered |
| F2C | Responsive/accessibility polish, old entry consolidation | ✅ Delivered |

See `docs/frontend-f2-planning.md`.

**F2A delivered**: Navigation restructured to Pilot/Ontology/工作区/更多工具. Pilot is default landing page. Project list + detail (goal/data stages). Dataset upload with multipart. Metadata-only profile display. API error handling (FormData support, human-readable errors). Minimalism & Swiss Style.

**Out of scope**: delete/recover, Object Runtime, SDK, MCP, Graph RAG, old feature removal, Pilot outcome/KPI dashboard, relation joins, Action execution, data write-back, custom query language.

## Phase 15: Evidence-to-Ontology Feedback Loop v1 ← COMPLETE

**Goal**: Turn useful project-scoped evidence into deliberate, auditable inputs for the Ontology semantic operating layer without automatic writes.

See `docs/phase15-planning.md`.

| # | Task | Description |
|---|------|-------------|
| 15.1 | Save scoped RAG answer as project evidence | ✅ Delivered. User-confirmed save from Pilot scoped Ask into `ProjectEvidenceLink` with `evidence_type=rag_run` and `role=decision`. Owner/admin-only write action. No auto-linking. |
| 15.2 | Project evidence review surface | ✅ Delivered. Pilot evidence summary distinguishes saved RAG answers from document evidence and shows type, role, saved time, safe provenance, and unavailable state without raw prompts/answers or path leaks. |
| 15.3 | Evidence-backed modeling draft candidate endpoint + UI | ✅ Delivered. Slice A: `POST /groups/{gid}/projects/{pid}/evidence-draft` creates proposed `OntologyModelingDraft` from active `ProjectEvidenceLink` records with bounded evidence_refs, safe provenance, idempotency. Slice B: frontend checkbox selection + proposal dialog in Pilot goal stage, owner/admin only. 22 backend tests + 53 UI tests pass. Design: `docs/phase15.3-design.md`. |

**Out of scope**: MCP runtime, Graph RAG, Agent auto-writing Ontology, external KB modification, full modeling studio, page hiding, LLM-only draft generation, auto-accept/publish.


## Phase 16: Pilot Outcome & FDE Delivery Record v1 ← PLANNED

**Goal**: Turn the completed Pilot workflow chain into a durable, auditable delivery record suitable for FDE handoff, interview demonstration, and portfolio evidence.

See `docs/phase16-planning.md`.

| # | Task | Description |
|---|------|-------------|
| 16.1 | Outcome record design / schema boundary | ✅ Delivered: PilotOutcomeRecord model, migration 0027, outcomes CR API, 40 tests. Evidences/packages validated; query_refs forbidden-key reject; bounded provenance. |
| 16.2 | Read-only outcome summary endpoint | ✅ Delivered: `GET /outcome-summary` on projects router. Aggregates project, latest outcome, evidence/package/runtime summaries. 13 new tests (53 total). No migration. |
| 16.3 | Pilot delivery report UI | Outcome panel in Pilot workspace: goal, evidence, model package, validation, query results, risks, next actions |
| 16.4 | Exportable interview/demo artifact | Concise delivery record for demo/interview; HTML/markdown first, no PDF dependency |

**Out of scope**: Graph RAG, MCP runtime, Agent auto-write, external KB write, autonomous publish, new framework/dependency, full PM system, full reporting engine.

**Next**: Implement 16.1 or review plan with project owner.

---

## Future Candidate: MCP Read-only Gateway v1 ← NOT STARTED

**Timing**: Candidate after Phase 13 review. The originally proposed Phase 12
number is no longer available because Phase 12 has already delivered Model
Quality & Contract Packages. A future phase number will be assigned only if the
Phase 13 review approves this direction.

**Candidate scope**:

- MCP server only; no client, external enterprise integration, or orchestration.
- Read-only `search_evidence`, `get_entity`, `list_relations`,
  `list_modeling_drafts`, and `get_governance_issues`.
- Authenticated caller mapping to Semantic Lighthouse user/group membership.
- Server-side `group_id` and role checks on every invocation.
- Durable invocation audit and bounded, provenance-preserving output.
- Shared service logic with REST/Agent paths; no direct table access or duplicated
  business rules.

**Not included**: writes, draft review/publish, Ontology mutation, external KB
repair, Graph RAG, CRM/ERP/BI integration, frontend UI, or multi-MCP orchestration.

See `docs/mcp-agent-boundary-design.md`. This candidate is planning context, not
authorization to implement runtime.


## Explicitly Out of Scope (current phases only)

**Goal**: Learn from LangChain Deep Agents / LangGraph without turning Semantic Lighthouse into a generic autonomous Agent platform.

| # | Task | Acceptance |
|---|------|------------|
| 7.R1 | Deep Agents pattern review | Adopt useful patterns only: todo/planning, context offloading, subagent isolation as future mode, HITL, and audit-friendly event flow |
| 7.R2 | Lightweight pattern adoption | Fold selected patterns into `plan_json`, `agent_steps`, risky confirmation, and `agent_loop()` without adding LangGraph runtime dependency |
| 7.R3 | Runtime adoption gate | LangGraph/Deep Agents runtime considered only after current FSM + LLM tool loop proves insufficient on measured multi-step scenarios |
| 7.R4 | Non-goal guardrail | No virtual filesystem, code execution sandbox, autonomous commit/deploy, broad multi-agent orchestration, or Agent bypass of backend permission rules |
| 7.R5 | V2.2 audit hardening | Add todo-like plan snapshots, risk metadata, truncated raw LLM response, and rejection observation tests to the existing Agent loop |

**Acceptance**: Agent Capability v2 can explain which Deep Agents ideas were adopted, which were rejected, and why the project still preserves group-scoped permission checks, audit trail, user confirmation, and deterministic backend rules.

---

## Explicitly Out of Scope (current phases only)

These items are not permanently rejected. They are deferred until the earlier engineering foundations are stable.

- Real-time collaboration (WebSocket, multi-user editing)
- Fine-tuning embedding or chat models
- On-premise LLM deployment (vLLM, Ollama)
- Kubernetes, service mesh, multi-region
- SSO / OAuth / SAML
- Billing, usage quotas, rate limiting
- Complex frontend SPA before Phase 6
- Open-ended complex Agent before Phase 7
- Automatic task creation from every answer
- Full project management system
- Autonomous web browsing or automatic web-to-KB ingestion
- LangGraph / Deep Agents runtime before measured FSM bottlenecks
- Full Ontology modeling studio before Phase 9 governance/graph is reliable
- Graph RAG before the entity/relation read model is reliable
- Agent auto-writing Ontology objects, relations, or actions
- Mobile app
- Multilingual RAG (current focus: English + Chinese where noted)

---

## Phase Transition Rules

A phase is complete when:
1. All acceptance criteria are met with passing tests.
2. `docs/agent-handoff.md` is updated with verification results.
3. A phase retrospective is written in `docs/engineering-memory/`.
4. The next phase's first task is de-risked (no blocking unknowns).
