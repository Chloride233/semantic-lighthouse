# Semantic Lighthouse — Project Roadmap

**Last updated**: 2026-06-18
**Current phase**: Phase 8 Experience Integration; next major phase is Phase 9 Ontology Core v1. See `docs/agent-handoff.md` and `docs/development-workflow.md`.

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

**Metrics**: 207 pytest, ruff clean, alembic `0011` at head. Production safety checks delivered (APP_ENV, JWT/cookie/database validation). verify_ui 19/22 (3 known-fragile: confirm button, task card, document metadata badges — none related to Phase 8).

---

## Product Alignment: Ontology Semantic Operating Layer ← UPDATED (2026-06-18)

**Goal**: Keep the project centered on the path from trusted evidence and user-confirmed action toward an enterprise Ontology semantic operating layer.

Ontology in this project means business objects, properties, relationships, actions, permissions, evidence, and Agent-facing interfaces. It is not just a database schema, not just a knowledge graph, and not just a RAG document library.

Current Phase 8 remains focused on the demonstrable loop:

```text
RAG answer -> user-confirmed task -> Agent/HITL -> audit trail
```

Next Phase 9 starts Ontology Core v1:

```text
schema/frontmatter validation -> entity extraction -> wikilink relation extraction -> broken-link detection -> ontology graph/entity detail
```

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

## Phase 8: Experience Integration ← CURRENT

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

## Phase 9: Ontology Core v1 - Governance & Graph ← NEXT

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


## Phase 7 Follow-up: Deep Agents Pattern Review ← DOCUMENTED

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
