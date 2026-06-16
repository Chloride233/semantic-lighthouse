# Semantic Lighthouse — Project Roadmap

**Last updated**: 2026-06-16
**Current phase**: Phase 7 delivered; next work should be chosen from retrieval quality, knowledge management, Agent eval, or deployment — see `docs/agent-handoff.md`

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

**Metrics**: 146 pytest, verify_ui 13/13, Alembic `0009_v9_rag_audit` (head). Eval: real ontology quality review plus citation-control regression tests.

---

## Phase 0: Engineering Baseline Stabilization ← CURRENT

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

## Phase 1: Retrieval Quality Engineering

**Goal**: The system can measure and improve what it retrieves.

| # | Task | Acceptance |
|---|------|------------|
| 1.1 | Hybrid search (keyword + vector fusion) | Configurable weights, measurable recall improvement |
| 1.2 | Rerank pass on retrieval results | Rerank model or cross-encoder, latency budget documented |
| 1.3 | Retrieval evaluation harness | Gold-standard Q&A pairs, recall@k, MRR, NDCG |
| 1.4 | Chunk overlap and context window tuning | Evidence that overlap improves retrieval on real documents |
| 1.5 | Embedding model comparison | Measured quality difference, cost/latency tradeoff |

**Acceptance**: `docs/retrieval-eval-report.md` with before/after metrics for at least 10 gold questions.

---

## Phase 2: Knowledge Governance & Document Lifecycle

**Goal**: Documents have a managed lifecycle and metadata that powers retrieval.

| # | Task | Acceptance |
|---|------|------------|
| 2.1 | Document metadata schema (entity type, status, source, tags) | Frontmatter validation, search/filter by metadata fields |
| 2.2 | Document deprecation and archival | `status=archived` excludes from search; soft-delete with audit |
| 2.3 | Group-level knowledge graph view | Entities and relations from ingested docs |
| 2.4 | DOCX table/header/footer extraction | Table content appears in chunks with structure preserved |
| 2.5 | Bulk import with progress tracking | `POST /import-local` returns job ID, async progress queryable |

**Acceptance**: Upload 50 documents, filter by metadata, archive stale ones, search excludes archived.

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

## Phase 4: V4 Agent Multi-Turn Dialogue

**Goal**: The system maintains conversation state and tool-use capability across turns.

| # | Task | Acceptance |
|---|------|------------|
| 4.1 | Conversation session management | `POST /conversations`, `POST /conversations/{id}/messages`, group-scoped |
| 4.2 | Multi-turn context window management | Sliding window or summarization; token budget enforced |
| 4.3 | Tool-use: search within conversation | Agent can call keyword/semantic search as a tool |
| 4.4 | Agent memory across sessions | User preferences, past questions, cited documents remembered |
| 4.5 | Agent audit trail | Every tool call, retrieved chunk, and generated response logged |

**Acceptance**: 5-turn conversation maintains context, cites documents from earlier turns, all actions auditable.

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

## Phase 7: Advanced Agent Orchestration ← DELIVERED (2026-06-13)

**Status**: 7.1–7.4 verified (10 tests, 6.5s). 3 tables, 8 API endpoints, tool registry, state machine, human-in-the-loop, memory. 7.5 (eval set) deferred to post-Phase 5.
**Goal**: Upgrade from controlled multi-turn RAG to explainable, auditable Agent workflows.

| # | Task | Acceptance |
|---|------|------------|
| 7.1 | Agent tool registry and permission policy | Every tool has input schema, role requirement, group boundary |
| 7.2 | Workflow planning with explicit state | Agent steps are planned, executed, and audited as separate records |
| 7.3 | Long-term memory governance | Memory has scope, retention, deletion, and citation rules |
| 7.4 | Human-in-the-loop checkpoints | Risky actions require approval before execution |
| 7.5 | Agent evaluation set | Multi-step tasks measured for success, citation quality, and failure handling |

**Acceptance**: A multi-step enterprise AI consulting workflow can be replayed, audited, and explained.

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
- Mobile app
- Multilingual RAG (current focus: English + Chinese where noted)

---

## Phase Transition Rules

A phase is complete when:
1. All acceptance criteria are met with passing tests.
2. `docs/agent-handoff.md` is updated with verification results.
3. A phase retrospective is written in `docs/engineering-memory/`.
4. The next phase's first task is de-risked (no blocking unknowns).
