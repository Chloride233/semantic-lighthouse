# Highlight Log

## Frontend Redesign Round 1 — Product Experience from Console

- Date: 2026-06-13
- Version: Phase 6.6
- Type: highlight
- Context: Frontend was a 6-page developer console with backend labels (RAG, Jobs) and a cold blue/gray palette. No onboarding or primary experience.
- What happened: Warm teal/amber visual system, tabbed auth with brand identity, guided onboarding, `/ask` as primary home with confidence bar and citation cards, user-task navbar labels. Every old page and route preserved. Zero npm, zero backend changes, 12/12 Playwright smoke tests pass.
- Engineering judgment: Additive redesign — CSS tokens upgrade all existing pages automatically. Old routes remain functional for compatibility. Product metaphor (lighthouse = guidance, warmth) now matches the visual language.
- Verification: `python scripts/verify_ui.py` → 12 passed, 0 failed.

## V1 Security Model Is Built Around Failure Modes

- Date: 2026-06-09
- Version: V1.0
- Type: highlight
- Context: The authentication system needed to support future permission-aware RAG retrieval.
- What happened: V1 implements short-lived Access Tokens, httpOnly Refresh Cookies, database-stored refresh token hashes, rotation, replay detection, and group role checks.
- Engineering judgment: Authentication is not just login. For enterprise RAG, identity must feed into authorization and later into retrieval filters.
- Risk if ignored: Future document retrieval could return or cite documents from groups the user should not access.
- Fix or control: Group APIs enforce authentication, membership role checks, and group_id-scoped queries.
- Verification: Tests cover refresh replay, role rejection, and non-member group access rejection.
- Interview version: I designed V1 auth as the security foundation for permission-aware RAG, not as tutorial JWT login.

## V1 Smoke Flow Reached A Running Service

- Date: 2026-06-09
- Version: V1.0
- Type: highlight
- Context: Automated tests had passed, but the service had not yet been exercised as a running API.
- What happened: Started the FastAPI service against a local SQLite database and completed register, login, `/auth/me`, and group creation.
- Engineering judgment: Tests prove logic, but a deliverable service must also start and accept real HTTP requests.
- Risk if ignored: The project could pass tests but still fail as an actual API service.
- Fix or control: Added dev start/stop scripts and performed a smoke flow through HTTP.
- Verification: `/health` returned `ok`; the smoke user created a group and received the `owner` role.
- Interview version: I separated unit/API regression from runtime smoke verification and confirmed the V1 API is usable end to end.

## Refresh Replay Was Verified Over HTTP

- Date: 2026-06-09
- Version: V1.0
- Type: highlight
- Context: Automated tests covered replay detection, but we also needed a running-service verification.
- What happened: Logged in, refreshed once to rotate the Refresh Token, replayed the old token, then tried the newer token again.
- Engineering judgment: The important behavior is not only that old tokens fail, but that replay is treated as session compromise.
- Risk if ignored: A stolen old Refresh Token could reveal compromise without invalidating the active session chain.
- Fix or control: The service returns 401 for old-token replay and revokes the newer token in the same family.
- Verification: HTTP smoke output showed `Refresh token replay detected` for both the old token replay and the newer token after family revoke.
- Interview version: I verified that Refresh Token Rotation handles the failure path, not just the happy path.

## Group Authorization Failure Paths Were Verified

- Date: 2026-06-09
- Version: V1.0
- Type: highlight
- Context: V1 needs to prove group permissions fail safely, not only that Owner actions work.
- What happened: Ran a HTTP smoke flow with Owner, Member, Applicant, and Outsider users.
- Engineering judgment: Permission systems are only credible when forbidden actions are tested.
- Risk if ignored: Member or non-member users could accidentally gain administrative or group-resource access, which would later become RAG document leakage.
- Fix or control: Membership and role checks returned 403 for Member join-request access, Member approval, and Outsider group access; Owner approval succeeded.
- Verification: HTTP smoke statuses: Member list requests 403, Member approve 403, Outsider get group 403, Owner approve 200.
- Interview version: I verified group authorization through negative paths, because future RAG retrieval will inherit this group boundary.

## V1 Passed PostgreSQL-Backed Runtime Verification

- Date: 2026-06-09
- Version: V1.0
- Type: highlight
- Context: SQLite tests and smoke flows were not enough to claim the enterprise persistence path worked.
- What happened: After fixing Docker/WSL/Hypervisor readiness, PostgreSQL started with Docker Compose and Alembic migrated the real Postgres database.
- Engineering judgment: A production-like runtime path must be verified separately from fast local tests.
- Risk if ignored: The project could pass tests while failing on its intended database backend.
- Fix or control: Ran PostgreSQL-backed smoke flows for normal auth/group flow, refresh replay, and group authorization failures.
- Verification: Postgres-backed smoke outputs showed register/login/me/create group succeeded, refresh replay returned 401 and revoked the family, and Member/Outsider authorization failures returned 403.
- Interview version: I verified V1 at three levels: automated tests, SQLite service smoke, and PostgreSQL-backed runtime smoke.

## V1.1 Auth Console Added For Manual Demo

- Date: 2026-06-10
- Version: V1.1
- Type: highlight
- Context: Swagger `/docs` was useful for debugging but not ideal as a project demo surface.
- What happened: Added a minimal `/console` static page for register, login, `/auth/me`, refresh, and logout.
- Engineering judgment: The frontend should demonstrate the V1 auth flow without becoming the main project complexity.
- Risk if ignored: The project would be technically usable but hard to demo outside API tooling.
- Fix or control: Used FastAPI static files and plain HTML/CSS/JS instead of adding a frontend framework.
- Verification: API tests still pass; `/console`, CSS, and JS load; HTTP smoke flow passed through register, login, `/auth/me`, refresh, and logout.
- Interview version: I added a minimal operations console to make the backend capability demonstrable while keeping the V1 focus on authentication and permissions.

## V2 Permission-Aware Document Retrieval

- Date: 2026-06-10
- Version: V2.0
- Type: highlight
- Context: V2 needs to give future RAG a safe document and chunk layer.
- What happened: Added group-scoped documents, group-scoped chunks, Markdown frontmatter parsing, heading-based chunking, local knowledge-base import, single Markdown upload, and keyword search.
- Engineering judgment: Retrieval safety must be proven before answer generation.
- Risk if ignored: RAG could later retrieve or cite documents outside the user's group.
- Fix or control: Every document and chunk carries `group_id`, and all list/detail/search queries filter by `group_id`.
- Verification: Tests cover member read access, Owner/Admin write access, non-member rejection, duplicate import, and cross-group search isolation.
- Interview version: I built retrieval safety before answer generation, because enterprise RAG needs permission-correct citations, not only factually correct text.

## V2.1 Semantic Retrieval Added Behind The Same Group Boundary

- Date: 2026-06-11
- Version: V2.1
- Type: highlight
- Context: V2 keyword search is explainable, but future RAG also needs semantic retrieval.
- What happened: Added an embedding client abstraction, Aliyun provider configuration, fake test provider, chunk embedding fields, rebuild endpoint, and semantic-search endpoint.
- Engineering judgment: Embedding generation should be separated from document ingestion so cloud API failures do not corrupt the document corpus.
- Risk if ignored: Vector retrieval could become a new cross-group leakage path or make imports unreliable.
- Fix or control: Semantic search still filters by `group_id`; tests use deterministic fake embeddings and cover non-member and cross-group failures.
- Verification: `pytest` passed with 26 tests; SQLite migration to `0003` passed; OpenAPI exposes rebuild and semantic-search; PostgreSQL + pgvector smoke passed; real Aliyun `text-embedding-v4` small-sample chain passed.
- Interview version: I added semantic retrieval without moving the permission boundary out of the database.

## V3 Single-Turn RAG Answer API

- Date: 2026-06-11
- Version: V3.0
- Type: highlight
- Context: After V2.1 semantic retrieval, the next useful milestone is a minimal answer-generation loop.
- What happened: Added a group-scoped RAG answer endpoint, DeepSeek-compatible chat provider, fake test provider, structured answer output, citation list, confidence, knowledge gaps, and next steps.
- Engineering judgment: Generation should consume retrieved citations instead of directly reading arbitrary documents or bypassing the permission layer.
- Risk if ignored: The model could produce uncited answers or accidentally use context from the wrong group.
- Fix or control: The answer endpoint checks membership, retrieves chunks with `group_id` filters, and passes only citation snippets into the chat provider.
- Verification: `pytest` passed with 31 tests; tests cover keyword RAG, semantic RAG, non-member rejection, cross-group isolation, and missing DeepSeek key errors.
- Interview version: I connected retrieval to generation while keeping the enterprise security boundary intact.

## V3.1 Local Evidence Gate

- Date: 2026-06-11
- Version: V3.1
- Type: highlight
- Context: A RAG system should not call the model when retrieval returns no evidence.
- What happened: Added a local no-evidence path that returns low confidence, knowledge gaps, next steps, and no citations.
- Engineering judgment: Refusing or deferring is part of answer quality, not a missing feature.
- Risk if ignored: The model could hallucinate a polished answer with no retrieved support.
- Fix or control: The RAG endpoint checks citations before creating a chat client or calling DeepSeek.
- Verification: Tests cover the no-evidence path under `CHAT_PROVIDER=deepseek` without needing `DEEPSEEK_API_KEY`.
- Interview version: I implemented a quality gate so the system can say “knowledge insufficient” instead of pretending.

## V3.2 Cloud Deployment Package

- Date: 2026-06-11
- Version: V3.2
- Type: highlight
- Context: The project needs a real cloud demo path after local V3 RAG passed.
- What happened: Added a production Dockerfile, Docker Compose deployment, production env template, Ubuntu bootstrap script, and deployment guide.
- Engineering judgment: A 2C2G ECS can run the API and pgvector for demo use because model inference stays on cloud APIs.
- Risk if ignored: The project would remain a local-only prototype and be harder to demonstrate in interviews.
- Fix or control: Keep deployment small: one API container, one PostgreSQL/pgvector container, one `.env.production`, one worker, and 2 GiB swap.
- Verification: Production Compose config renders successfully; full test suite still passes with 33 tests; cloud deployment reached healthy API and PostgreSQL containers on Alibaba Cloud ECS.
- Interview version: I containerized the RAG prototype for a small ECS without overbuilding platform infrastructure before the product loop is stable.

## V3.2 Alibaba Cloud ECS Deployment Verified

- Date: 2026-06-11
- Version: V3.2
- Type: highlight
- Context: The local RAG prototype needed a real public demo endpoint.
- What happened: Deployed the API and PostgreSQL/pgvector to an Alibaba Cloud ECS instance with Docker Compose.
- Engineering judgment: For a 2C2G server, model inference stays on external APIs while the server runs only API, database, migration, and health checks.
- Risk if ignored: A local-only project is harder to demonstrate and does not prove basic deployment ability.
- Fix or control: Added 2 GiB swap, used one API worker, ran Alembic migrations on startup, and verified container health.
- Verification: `/docs` is reachable from the public IP; API and PostgreSQL containers are healthy; migrations reached `0003_v21_embeddings`.
- Interview version: I completed a real cloud deployment and verified the runtime stack instead of only showing local tests.

## V3.2 Real Cloud RAG Smoke Passed

- Date: 2026-06-11
- Version: V3.2
- Type: highlight
- Context: After cloud deployment, the project needed proof that the real provider chain worked, not only fake-provider tests.
- What happened: Ran a real cloud smoke chain: register, login, create group, upload Markdown, rebuild embeddings, semantic search, and RAG answer.
- Engineering judgment: Provider integration should be tested with a small controlled sample after local fake-provider regression passes.
- Risk if ignored: The system could pass local tests but fail at the actual cloud API, pgvector, or model-generation boundary.
- Fix or control: Used one small Markdown document and a narrow semantic query to limit cost while validating the full path.
- Verification: DeepSeek returned a grounded answer explaining why Ontology is still useful when an enterprise already has a data platform.
- Interview version: I verified the full production-like RAG chain with real cloud embedding and chat providers on the deployed ECS service.

## V3.3 RAG Run Audit Added

- Date: 2026-06-11
- Version: V3.3
- Type: highlight
- Context: A RAG answer should be replayable and auditable after it is generated.
- What happened: Added `rag_runs`, persisted RAG answers, returned `run_id`, and exposed group-scoped run list/detail APIs.
- Engineering judgment: Historical questions, answers, and citations are enterprise data and must inherit group permissions.
- Risk if ignored: The system could answer questions but provide no way to debug retrieval quality or explain past outputs.
- Fix or control: Store answer, confidence, retrieval method, model, citations, knowledge gaps, next steps, user ID, group ID, and timestamp.
- Verification: `pytest` passed with 35 tests; Alembic migrated from empty SQLite DB to `0004_v33_rag_runs`.
- Interview version: I added auditability to the RAG chain so answers can be reviewed, replayed, and evaluated.

## V2.2 Chunked Multi-Format Upload Added

- Date: 2026-06-11
- Version: V2.2
- Type: highlight
- Context: The document layer needed more than small Markdown upload to support realistic enterprise materials.
- What happened: Added MD/TXT/PDF/DOCX parsing, three-stage chunked upload, instant upload, resumable sessions, idempotent chunk writes, and local disk storage volumes.
- Engineering judgment: Large file handling should be a protocol with integrity checks, not only a larger request size limit.
- Risk if ignored: Upload failures would force full retransmission, duplicate files could pollute retrieval, and parsing failures could create half-ingested documents.
- Fix or control: `init` checks hash and session progress, `chunks` upserts by chunk index, and `complete` verifies chunk completeness plus final SHA-256 before ingestion.
- Verification: `pytest` passed with 40 tests; Alembic migrated from empty SQLite DB to `0005_v22_chunked_uploads`.
- Interview version: I turned document upload into a resumable, auditable ingestion protocol while keeping group-level data isolation.
## V3.4 ETL Pipeline Hardened — Retrospective Review Caught Production Blockers

- Date: 2026-06-12
- Version: V3.4
- Type: highlight
- Context: After the initial V3.4 ETL delivery, a structured code review found six bugs (P1-1 to P2-3), including a NameError that would crash PostgreSQL semantic search and a retry bypass that made the 3-attempt loop dead code for embedding failures.
- What happened: Three CRITICAL bugs were fixed: (1) `PGVECTOR_DIMENSION` undefined in pgvector code paths — hidden by SQLite fallback; (2) `EmbeddingError` caught and short-circuited the retry loop; (3) manual retry on a ready document could destroy existing search results. Three additional quality issues were fixed: step_log mutation not tracked, test assertions too loose to catch failures, and ETL scope not documented.
- Engineering judgment: A review that explicitly hunts for "why would this pass tests but fail in production?" uncovered issues that a green test suite alone would miss. The pgvector NameError is the archetype: SQLite fallback tests are fast but create a blind spot for dialect-specific code paths.
- Risk if ignored: Production deployment would crash on first semantic search request; transient cloud API errors would cause permanent ingestion failures; operators could accidentally take down working search results.
- Fix or control: All P1/P2 bugs fixed with regression tests. Test suite now uses file-backed SQLite to support BackgroundTasks across threads. Ruff lint zero errors. Migration at head.
- Verification: 55 passed, 1 warning; ruff clean; Alembic 0006 at head.
- Interview version: I learned that a green test suite is necessary but not sufficient for deployment confidence. Dialect-specific code paths need a separate smoke gate; every step in a retry loop must propagate errors; and destructive operations on production data need a safety net.

## V2.2 Upload Cleanup And Memory Safety Hardened

- Date: 2026-06-11
- Version: V2.2
- Type: highlight
- Context: V2.2 chunked upload worked functionally but had three engineering gaps: no temp file cleanup, no merged-file cleanup on failure, and full-file memory loading for hash verification.
- What happened: Added streaming hash verification (`verify_file_hash`), temp chunk cleanup (`cleanup_upload_temp_dir`), merged-file cleanup on failure (`cleanup_merged_file`), and tightened upload session GET permission from any Member to Owner/Admin.
- Engineering judgment: Upload correctness includes cleanup, not just ingestion success. Memory safety matters even at 50 MiB limits when the server has only 2 GiB total.
- Risk if ignored: Disk leak in `upload-tmp` and `document-storage`, OOM risk from concurrent upload hash verification, and asymmetric permission surface exposing upload metadata to members.
- Fix or control: Three cleanup paths (success, hash-mismatch, parser-failure) each handle both temp and merged files appropriately. Hash verification streams in 64 KB chunks. Permission aligned across all upload endpoints.
- Verification: 44 tests pass (4 new: cleanup after success, cleanup after hash mismatch, cleanup after parser failure, member GET rejection). Migration smoke clean at `0005_v22_chunked_uploads`.
- Interview version: I hardened the upload chain across three dimensions — disk hygiene, memory safety, and permission consistency — so the protocol is not just functional but resilient under concurrent use on a small server.

## V4.0 Multi-Turn Conversation Memory

- Date: 2026-06-12
- Version: V4.0
- Type: highlight
- Context: After V3 RAG single-turn was stable, the next engineering step was multi-turn conversation memory — not a fully autonomous agent, but a controlled mechanism for maintaining context across turns.
- What happened: Added `conversations` + `conversation_messages` tables with `group_id`/`user_id` isolation; 4 API endpoints (create, list, get detail, send message); multi-turn history injection into LLM prompts via `history` parameter on `ChatClient.answer_question`; full audit trail via message persistence.
- Engineering judgment: Multi-turn should extend the existing RAG pipeline (retrieve → cite → generate → audit) rather than replace it. Conversation memory inherits the same `group_id` boundary and user-level isolation that every other data path enforces. History injection is a prompt-layer concern, not a new storage or state management layer.
- Risk if ignored: Building a full agent framework before conversation basics would couple tool-calling, memory governance, and workflow planning into a single delivery, making each layer harder to test and explain independently.
- Fix or control: History limited to 10 rounds (20 messages); user-scoped ownership enforced on all GET/POST paths; `ChatClient.answer_question` accepts optional `history` parameter with backward-compatible default; no-change to existing RAG single-turn API.
- Verification: 91 passed (77 existing + 14 new), 0 failures; ruff clean; Alembic migrated from empty SQLite DB to `0007_v4_conversations` (head).
- Interview version: I added multi-turn conversation memory as a thin extension of the RAG audit chain — same permission boundary, same retrieval pipeline, same citation generation — so the system can sustain a consulting dialogue without a heavyweight agent framework.

## V4.1 Controlled Tool Calling

- Date: 2026-06-12
- Version: V4.1
- Type: highlight
- Context: After V4.0 conversation memory was stable, the next step was letting the Agent request predefined tools — without building a full autonomous agent framework.
- What happened: Added a server-side tool registry (`AVAILABLE_TOOLS`) with one tool (`search_knowledge_base`). Extended `ChatClient` with `generate_response()` that returns either a direct `ChatAnswer` or a `ToolCall`. Implemented a single-level tool loop in `send_message`: LLM requests tool → server executes with `group_id` boundary → tool result injected into conversation history → LLM produces final answer. Tool execution and results are persisted as `ConversationMessage` records with `role="tool"` and `tool_calls` JSON for audit.
- Engineering judgment: Tool calling should be a deterministic server-side execution, not a model-controlled sandbox. The tool registry is a hardcoded whitelist; unknown tools return errors. The loop depth is bounded at 1 (no recursion). All tool searches inherit the caller's `group_id` permission — the model can't escape its data boundary.
- Risk if ignored: Without tool calling, the Agent is limited to the initial retrieval, which may miss relevant results. But with unrestricted tool access, the model could attempt dangerous actions or access cross-group data.
- Fix or control: Whitelist-only tool registry; `_execute_tool` validates tool name before execution; tool results capped at 2000 characters; `_messages_with_tools` instructs the model to request at most one tool; final answer path degrades gracefully if no answer produced.
- Verification: 96 passed (91 existing + 5 new tool tests), 0 failures; ruff clean; all existing conversation tests pass without modification.
- Interview version: I added controlled tool calling as a server-side gate rather than a model-side capability — the Agent can ask for help, but the server decides what's safe to execute.

## Phase 6 Frontend Engineering Console

- Date: 2026-06-12
- Version: V6.0
- Type: highlight
- Context: After backend phases 0-4.1 stabilized, the project needed a real, maintainable frontend for demo and operations — not a throwaway Swagger-only experience.
- What happened: Built a complete SPA console using vanilla JS ES modules with a hash-based client router. Six pages cover the full demo flow: Auth (login/register), Groups (list/create/join), Documents (upload/search/archive), Ingestion Jobs (list/detail/retry), RAG (question → answer → citations → confidence → knowledge gaps), and Conversations (list + multi-turn chat with tool call display). Zero npm dependencies, zero build step — served directly by FastAPI's existing StaticFiles mount.
- Engineering judgment: A frontend for a backend-heavy prototype should be as lightweight as the backend's own toolchain. Adding a React/Vue build pipeline for 6 CRUD pages would burden future maintainers with node_modules, webpack configs, and version drift. ES modules are native, `/console` loads instantly, and the module-per-page structure is trivially extensible.
- Risk if ignored: Without a real UI, every demo requires Swagger + curl — unusable for non-engineers and unconvincing in interviews. But building a "big admin panel" would add maintenance debt disproportionate to the project's stage.
- Fix or control: Vanilla JS ES modules, hash-based routing (~50 lines), shared CSS custom properties, one file per page/component. Permission-aware: Owner/Admin see archive/retry buttons; Members don't. Auth state drives navbar visibility. No backend changes required.
- Verification: 96 backend tests pass (zero regression); ruff clean; all 11 frontend files load via ES module imports; `/console` serves the new SPA.
- Interview version: I built a real frontend console without installing a single npm package — the same `uvicorn` command that serves the API also serves the SPA, and the module-per-page structure keeps the codebase explainable.

## Phase 7 Agent Orchestration — Lightweight State Machine

- Date: 2026-06-12
- Version: V7.0
- Type: highlight
- Context: After V4.1 single-tool Agent was stable, the next step was multi-step Agent workflows with explicit state, audit trail, human-in-the-loop, and long-term memory — without introducing LangGraph or AutoGen.
- What happened: Built a lightweight FSM (plan→execute→observe→conclude) on SQLAlchemy. Added 3 tables, 8 API endpoints, and a 3-tool registry with role requirements and risk flags. Every step records: thought, action_type, action_detail, observation, status, and error_message. Human-in-the-loop: risky tools pause the run; user confirms/rejects via API.
- Engineering judgment: The workflow is linear — not a DAG, not multi-agent. A 50-line state machine with persisted transitions is more explainable than LangGraph's StateGraph with checkpointers. Framework cost (dependency, mental model, serialization contract) is not justified by problem complexity.
- Risk if ignored: Without step-level auditing, multi-tool Agent runs are black boxes — impossible to debug why a search failed or what the Agent was "thinking" at each step.
- Fix or control: Every step has immutable `thought`. Failed steps have `error_message`. Risky tools flagged `is_risky=True`. Human confirmation recorded as `action_type=ask_user`. Memory scoped user/group with TTL.
- Verification: 10 agent tests pass; ruff clean; Alembic at `0008_v7_agent_orchestration`.
- Interview version: I built a multi-step Agent orchestrator as a deterministic state machine — when something goes wrong, you read every step the Agent took, not guess.

## Claude Code Handoff Memory Established

- Date: 2026-06-11
- Version: Handoff
- Context: The project may move from Codex-led development to Claude Code-led development.
- What happened: Added `CLAUDE.md`, `docs/agent-handoff.md`, and `docs/engineering-memory/learning-index.md` so a new coding agent can recover project intent, current state, verification results, risks, and next steps without relying on chat history.
- Engineering judgment: Agent memory should live in repo-owned documentation, not in transient conversations. The handoff path must be short enough to read but specific enough to constrain future work.
- Risk if ignored: A new agent could duplicate work, skip tests, introduce unexplained architecture, or miss the current V2.2 upload-chain risks.
- Fix or control: `CLAUDE.md` defines the read order and working rules; `agent-handoff.md` stores current state and next priority; `learning-index.md` summarizes practiced concepts and weak points.
- Verification: `pytest` passed with 40 tests; Alembic migrated from empty SQLite DB to `0005_v22_chunked_uploads`.
- Interview version: I treated AI-assisted development handoff as an engineering artifact, so project memory, risk state, and verification results are reproducible across tools and sessions.
