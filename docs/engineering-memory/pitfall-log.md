# Pitfall Log

## Draft FKs Cannot Depend Directly On Scan-Rebuilt Read-Model IDs

- Date: 2026-06-19
- Version: Phase 11.1+11.2
- Type: pitfall → **FIXED**
- Context: `OntologyModelingDraft` FK columns (`source_entity_id`, `source_relation_id`, `source_issue_id`) pointed to `ontology_entities`, `ontology_relations`, `ontology_validation_issues` — tables that `scan_group()` deletes and rebuilds on every scan.
- What happened: Without the fix, rescan would (a) fail on PostgreSQL with strict FK enforcement because deletes target records still referenced by drafts, or (b) silently leave dangling FK pointers on SQLite (default FK=OFF). Draft evidence linkage broken after any rescan.
- Engineering judgment: FKs to records with shorter lifecycle than referencing rows are a design hazard. Drafts should survive scans. FK should reflect current evidence identity, not creation-time identity.
- Risk if ignored: Every rescan (normal ops: scan→triage→curate→rescan) would crash or corrupt draft evidence links. Modeling draft feature unusable.
- Fix or control: `scan_group()` preserves evidence via stable keys: entity→`document_id`, relation→`(source_document_id, target_path, target_label, relation_type)`, issue→`issue_key`. Before deleting: null FKs+flush, delete with intermediate flushes (FK-safe order), rebuild, relink via stable keys. If evidence vanished, source pointer stays null. No ON DELETE SET NULL migration — service-level relink is the primary control.
- Verification: 10 new tests (entity/relation/issue relink, vanished evidence, metadata preservation, rag_run unaffected, cross-group isolation, PRAGMA foreign_keys=ON regression). 67 related pass. Full suite 307/311 (4 pre-existing E2E). Ruff clean.

## Handoff Baseline Pointer Can Drift After Documentation Commits

- Date: 2026-06-16
- Version: Handoff
- Type: pitfall -> fixed
- Context: A takeover check found that `docs/agent-handoff.md` still named `77921da feat: improve rag citation control` as the latest code baseline even though `d45bef4 docs: refresh project handoff entrypoints` was already HEAD.
- What happened: The handoff content had been refreshed, but the final "latest code baseline" sentence was not updated with the actual repository HEAD.
- Engineering judgment: Handoff files are operational state, not passive notes. A stale commit pointer can make the next agent trust the wrong snapshot or repeat already-completed verification.
- Risk if ignored: New sessions could chase a false dirty-state problem, overlook newer documentation changes, or report inconsistent baselines in final summaries.
- Fix or control: Updated `docs/agent-handoff.md` with the current verification results and changed the baseline sentence to the latest verified pre-refresh commit.
- Verification: `pytest` full suite passed 146 tests; `scripts/verify_ui.py` passed 13/13; ruff clean; encoding scan clean; Alembic migrated an empty SQLite DB to `0009_v9_rag_audit (head)`.
- Interview version: I treated project handoff as a tested artifact and corrected a stale commit pointer before starting new feature work.

## Two Search Endpoints With Different Semantics

- Date: 2026-06-14
- Version: Phase 1 (P3 eval)
- Type: pitfall → **NOTED** (design awareness)
- Context: Two keyword search paths: `GET /search` (simple ILIKE substring on raw query) vs `hybrid_search()` (term extraction + OR conditions). P3 eval initially used `/search` and got 0% recall on Chinese questions.
- What happened: `WHERE chunk.content ILIKE '%完整的19字中文问题%'` requires verbatim substring match. Natural questions never appear as literal substrings in documents.
- Engineering judgment: `/search` is for exact-match debugging. `hybrid_search` is for NLP queries. They serve different purposes.
- Fix: P3 eval uses `GET /search/hybrid` with `keyword_weight` to isolate strategies. No code change.

## Failed RAG Calls Left No Audit Trail — 502 Without Record

- Date: 2026-06-14
- Version: Phase 3 (P2 QA audit)
- Type: pitfall → **FIXED**
- Context: RAG answer endpoint had three code paths: no-evidence, success, ChatError. Only the first two persisted to `rag_runs`.
- What happened: When the LLM provider returned an error (missing API key, timeout, rate limit), the endpoint raised `HTTPException(502)` without writing to `rag_runs`. The user's question, retrieved citations, retrieval method, and failure reason were all lost — there was no way to know who asked what, when, or why it failed.
- Engineering judgment: Audit is not only about successful answers. Failures are arguably more important to audit — they reveal systemic issues (missing keys, provider outages) and user behavior (questions that keep failing). If every success is recorded but failures are silent, the audit trail tells an incomplete and misleading story.
- Risk if ignored: An operator looking at `GET /rag/runs` would see only successes, creating the illusion that the system never fails. Debugging a provider outage would require correlating HTTP access logs with application state — fragile and manual.
- Fix or control: Added `_persist_failed_run()` called in the `except ChatError` block before re-raising. New columns on `rag_runs`: `status` (success/no_evidence/error), `error_message`, `duration_ms`, `retrieved_count`. Migration `0009_v9_rag_audit`. Three new tests: success path audit fields, failed run persisted + group-isolated, no-evidence path audit status.
- Verification: 113 backend pass, 22 RAG tests (3 new audit tests). Failed runs are now queryable via existing `GET /runs` + `GET /runs/{id}`.
- Interview version: I treated the absence of failure records as an audit integrity gap — the audit trail must be complete across all code paths, not just the happy path.

## RAG Output Contract Is More Important Than "Model Can Answer"

- Date: 2026-06-14
- Version: Phase 3 (P1 hardening)
- Type: pitfall → **FIXED**
- Context: RAG system prompt was English, fake provider could leak raw English snippets into Chinese answer skeleton, frontend confidence display had 6 bugs (falsy fallback, dead code, 0.000 score display, enum leak, empty answer).
- What happened: A full-chain review (system prompt → LLM → fake provider → API response → frontend) found that individual pieces worked in isolation but together produced: English prompt-text leakage, contradictory "medium confidence (0)" display, citation score `0.000` rendered literally, raw enum strings through badge fallback.
- Engineering judgment: The RAG output contract defines what the user sees. If the contract is broken on edge cases, the system fails its core promise of being an enterprise AI consulting advisor. The system prompt is part of the contract — English in the prompt can echo into user-facing JSON. The fake provider is the local demo path; if it leaks English, the primary demo experience is broken even though DeepSeek might work.
- Risk if ignored: In a demo — user uploads English doc → asks question → sees "Based on retrieved sources..." → product looks like a debug tool, not an advisor. `confidence: null` + score: 0 = "中等可信 (0)" — contradictory and misleading.
- Fix or control: Chinese system prompt with explicit English-phrase prohibitions. `_summarize_citation_text` detects ASCII-heavy snippets → Chinese summary. Frontend: Set-based level validation, `'unknown'` state, empty-answer placeholder, citation score hide when ≤ 0. 3 new contract tests.
- Verification: 110 backend pass, ruff clean, 19 RAG tests (3 new contract tests). Full regression green.
- Interview version: The RAG output contract spans system prompt → fake provider → frontend render. Testing the *absence* of English phrases is a contract test, not a QoL improvement. The fake provider defines the demo experience; it must satisfy the same contract as the real provider.

## Phase 0 Baseline: pgvector Smoke Pending Docker Daemon

- Date: 2026-06-12
- Version: Phase 0
- Type: pitfall (environment) → **RESOLVED**
- Context: Phase 0 required real PostgreSQL + pgvector smoke to verify P1-1 and HNSW index.
- Resolution: Docker Desktop started successfully. Full smoke chain ran: register → login → group → upload → keyword search → semantic search. PGVECTOR_DIMENSION import verified — No NameError on real pgvector. HNSW index `m=16, ef_construction=200` confirmed in `pg_indexes`. Alembic reached `0006 (head)` on PostgreSQL.
- Verification: Semantic search endpoint exercised the `<=>` operator path without error. Keyword search returned expected result. Upload → ETL → ready completed successfully.
- Interview version: I confirmed the dialect-specific code path on real PostgreSQL after fixing a NameError that SQLite tests couldn't catch. SQLite tests are fast; PostgreSQL smoke is the deployment gate.

## SQLite Tests Cannot Cover PostgreSQL-Specific Code Paths

- Date: 2026-06-12
- Version: V3.4
- Type: pitfall
- Context: After extracting shared router helpers, `PGVECTOR_DIMENSION` was renamed to `_PGVECTOR_DIMENSION` (private), but `documents.py:698` and `rag.py:280` still referenced the old public name.
- What happened: All 54 tests passed because the semantic-search PostgreSQL code paths use `db.bind.dialect.name == "postgresql"` guard and fall back to Python on SQLite. The NameError would only trigger on a real PostgreSQL/pgvector deployment.
- Engineering judgment: Dialect-specific code paths need either a PostgreSQL-backed smoke test or static analysis that can detect undefined names in all branches. The current SQLite-only test suite is necessary for speed but insufficient for deployment confidence.
- Risk if ignored: Deploying to production PostgreSQL would crash semantic-search and semantic RAG with a NameError on the first request.
- Fix or control: Renamed `_PGVECTOR_DIMENSION` → `PGVECTOR_DIMENSION` and added explicit imports in both routers. Added a note in `agent-handoff.md` that cloud smoke verification (per `docs/cloud-smoke-playbook.md`) must cover the pgvector code paths.
- Interview version: I learned that SQLite fallback tests are fast and convenient but create blind spots for dialect-specific SQL. The right pattern is fast local tests + a PostgreSQL smoke gate before deployment.

## Embedding Failure Bypassed The Retry Loop

- Date: 2026-06-12
- Version: V3.4
- Type: pitfall
- Context: The ETL pipeline has a 3-attempt retry loop with exponential backoff, but the embedding step had its own `except EmbeddingError: _fail_job(); return` that short-circuited the retry.
- What happened: `EmbeddingError` (e.g., Aliyun API timeout) would immediately mark the job as `failed` on the first attempt, never retrying. This made the retry loop dead code for the most common failure mode.
- Engineering judgment: Inner exception handlers that call `_fail_job()` and return are "retry killers". Every ETL step should propagate errors to the outer retry loop unless the error is permanently unrecoverable (e.g., "file not found", "document deleted").
- Risk if ignored: Transient cloud API errors (rate limits, timeouts, DNS) would cause permanent ingestion failures, requiring manual retry for every hiccup.
- Fix or control: Removed the inner `except EmbeddingError` handler; `EmbeddingError` now propagates to the outer `except Exception` that drives the `for attempt in range(...)` retry loop. Added `test_etl_retries_then_succeeds` with a monkeypatched fake provider that fails twice then succeeds, asserting `attempt_count=3` and `status=succeeded`.
- Interview version: I treated every ETL step failure as retryable by default and only skipped retry for unrecoverable conditions (document not found). The test proves the retry loop actually works instead of only testing the happy path.

## Manual Retry Could Destroy A Working Document

- Date: 2026-06-12
- Version: V3.4
- Type: pitfall
- Context: `POST /ingestion-jobs` (manual retry) unconditionally set `document.status = "uploaded"`, removing the document from search/RAG results.
- What happened: If an owner clicked "retry ingestion" on an already-ready document and the ETL failed, the document would become `failed` — permanently invisible to search and RAG despite having valid chunks before the retry.
- Engineering judgment: A retry operation must not be more destructive than the original upload. If the document was already serving search traffic, the retry should work on a "shadow" copy and only swap in the new version on success.
- Risk if ignored: Operators would be afraid to retry ingestion because a failure could take down existing search results. The system would accumulate stale-but-working documents that could never be re-processed.
- Fix or control: `create_ingestion_job` no longer changes `document.status` for ready documents. `run_etl_job` tracks `was_ready` and on final failure restores `status = "ready"` (old chunks intact). On success, chunks are atomically replaced in a single transaction. Added `test_ready_document_survives_failed_retry` that proves keyword search still works after a failed retry on a ready document.
- Interview version: I made retry safe for production traffic by treating the existing document version as the fallback. The new version only replaces the old one after every ETL step succeeds.

## PostgreSQL pgvector SQL Needed Real Runtime Verification

- Date: 2026-06-11
- Version: V2.1
- Type: pitfall
- Context: SQLite tests passed for semantic search using Python fallback, but real PostgreSQL uses pgvector SQL.
- What happened: The first PostgreSQL smoke exposed two issues: an unbound `:query_vector` inside raw SQL and a distance expression being processed as a vector instead of a float.
- Risk if ignored: V2.1 would appear correct in tests but fail in the intended PostgreSQL runtime.
- Fix or control: Switched to SQLAlchemy bind parameters with pgvector casting and explicitly cast the distance expression to `Float`.
- Verification: PostgreSQL-backed smoke passed through register, login, group creation, upload, embedding rebuild, and semantic search.
- Interview version: I learned that SQLite fallback tests cannot prove dialect-specific vector SQL. I kept fast tests local, but added a PostgreSQL smoke path for pgvector behavior.

## V1 Dependency Reality Check

- Date: 2026-06-09
- Version: V1.0
- Type: pitfall
- Context: The project moved from planning to implementation on a clean Windows workspace.
- What happened: The machine had Python 3.14 and Git, but no FastAPI, SQLAlchemy, pytest, Docker, uv, Poetry, or local PostgreSQL.
- Engineering judgment: A project is not credible because a plan says "use PostgreSQL"; it becomes credible when the runtime and dependency boundary are explicit.
- Risk if ignored: The team could write code that cannot run, making V1 a paper design instead of a usable authentication system.
- Fix or control: Added dependency manifests, Docker Compose for PostgreSQL, and a pytest setup that can run against SQLite for fast API-level regression tests.
- Verification: Dependency installation and test execution are the next required checkpoint.
- Interview version: I treated runtime availability as part of engineering delivery, not an afterthought.

## JWT Secret Length Warning

- Date: 2026-06-09
- Version: V1.0
- Type: pitfall
- Context: The first V1 test run passed functionally but PyJWT emitted an HMAC key-length warning.
- What happened: The test secret was only 11 bytes, below the recommended minimum for HS256.
- Engineering judgment: Passing tests are not enough if the security library is telling us the configuration is weak.
- Risk if ignored: A short symmetric signing key weakens JWT integrity and teaches the wrong deployment habit.
- Fix or control: Increased the default and test JWT secret values to at least 32 bytes.
- Verification: Re-run pytest and confirm the HMAC key-length warning is gone.
- Interview version: I treated security warnings as engineering feedback, not noise to ignore.

## Alembic Needs The src Package Path

- Date: 2026-06-09
- Version: V1.0
- Type: pitfall
- Context: Alembic migration verification failed after the application tests passed.
- What happened: `alembic upgrade head` could not import `semantic_lighthouse` because the project uses a `src/` layout.
- Engineering judgment: Runtime tests and migration tests exercise different parts of the system; a service is not deployable if migrations cannot import the model metadata.
- Risk if ignored: The API could work in tests while the production database cannot be initialized.
- Fix or control: Set Alembic `prepend_sys_path = src` so migration commands can import the application package.
- Verification: Re-run Alembic migration against a temporary SQLite database and later against PostgreSQL when Docker is available.
- Interview version: I verified the deployability path separately from API tests and caught a migration environment issue early.

## Tests Passing Is Not The Same As App Importability

- Date: 2026-06-09
- Version: V1.0
- Type: pitfall
- Context: API tests passed because pytest had `pythonpath = src`, but a direct app import failed.
- What happened: The package was not installed into the virtual environment, so `semantic_lighthouse.main` was unavailable outside pytest.
- Engineering judgment: A project is not usable if it only works under the test runner's import path.
- Risk if ignored: The service could pass tests but fail when started with Uvicorn.
- Fix or control: Added setuptools package metadata and documented `pip install -e .` in the local setup.
- Verification: Install the package in editable mode and import `semantic_lighthouse.main` from the venv.
- Interview version: I separated test convenience from runtime packaging and made the service startable like a normal Python app.

## Docker Is A Real V1 Acceptance Dependency

- Date: 2026-06-09
- Version: V1.0
- Type: pitfall
- Context: V1 is designed to run PostgreSQL via Docker Compose.
- What happened: The workstation does not currently expose a `docker` command.
- Engineering judgment: SQLite tests prove application logic, but they do not prove the final PostgreSQL runtime path.
- Risk if ignored: The project could claim enterprise persistence while only being tested on an in-memory database.
- Fix or control: Keep Docker Compose and Alembic configuration in the repo, mark PostgreSQL-backed verification as open until Docker is installed.
- Verification: After Docker is available, run `docker compose up -d postgres`, `alembic upgrade head`, and a smoke flow through `/docs`.
- Interview version: I separated fast regression tests from production-like runtime verification and did not overclaim the unverified part.

## Docker Desktop Install Requires Admin Readiness

- Date: 2026-06-09
- Version: V1.0
- Type: pitfall
- Context: We attempted to install Docker Desktop through Chocolatey to complete PostgreSQL Compose verification.
- What happened: Chocolatey was not running from an elevated shell and failed on `C:\ProgramData\chocolatey` lock/directory permissions.
- Engineering judgment: Production-like verification depends on workstation infrastructure. When the machine is not ready, the honest response is to mark the environment blocker instead of pretending the runtime path is verified.
- Risk if ignored: The project would overclaim Docker/PostgreSQL readiness while only SQLite smoke verification has passed.
- Fix or control: Installed Docker Desktop from an Administrator PowerShell, then fixed WSL2/Hypervisor readiness before rerunning PostgreSQL verification.
- Verification: Completed. Docker Engine started, PostgreSQL Compose ran, Alembic migrated PostgreSQL, and HTTP smoke flows passed.
- Interview version: I learned to separate application correctness from environment readiness and to record infrastructure blockers explicitly.

## WSL2 Requires Windows Hypervisor, Not Just BIOS Virtualization

- Date: 2026-06-09
- Version: V1.0
- Type: pitfall
- Context: Docker Desktop continued to report "Virtualization support not detected" even though BIOS virtualization was enabled.
- What happened: WSL2 failed with `HCS_E_HYPERV_NOT_INSTALLED`; `hypervisorlaunchtype` was set to `Off`.
- Engineering judgment: Virtualization readiness has multiple layers: BIOS support, Windows optional features, WSL2 distribution, and Hypervisor launch configuration.
- Risk if ignored: The team could waste time reinstalling Docker or Ubuntu while the real blocker is Windows boot configuration.
- Fix or control: Set `bcdedit /set hypervisorlaunchtype auto`, rebooted, and verified `wsl -d Ubuntu -- uname -a` plus `Ubuntu Running VERSION 2`.
- Verification: Docker Engine reported both Client and Server, and PostgreSQL ran through Docker Compose.
- Interview version: I debugged the runtime stack layer by layer instead of treating Docker as a black box.

## Dev Start Script Had Windows Environment Edge Cases

- Date: 2026-06-09
- Version: V1.0
- Type: pitfall
- Context: The API had to be started repeatedly against SQLite and PostgreSQL during smoke verification.
- What happened: Windows PowerShell exposed several script issues: `$PID` is read-only, `Path/PATH` duplicate environment keys broke `Start-Process`, and `ProcessStartInfo` environment handling differed across versions.
- Engineering judgment: Local developer scripts are part of deliverability. A backend is harder to verify if start/stop commands are fragile.
- Risk if ignored: Future smoke tests could fail for environment/tooling reasons instead of application reasons.
- Fix or control: Renamed `$pid` to `$processId`, removed duplicate `Env:PATH` before `Start-Process`, and added log redirection.
- Verification: PostgreSQL-backed API could be started for smoke testing; when scripts were still brittle, a one-command start/smoke/stop flow was used for reliable verification.
- Interview version: I treated local operability scripts as engineering assets, not disposable command snippets.

## Browser/Frontend Verification Tooling Was Limited

- Date: 2026-06-10
- Version: V1.1
- Type: pitfall
- Context: A frontend page was added and should be verified with Playwright.
- What happened: `playwright-cli` was not available in PATH, and no in-app browser control tool was exposed in the current tool set.
- Engineering judgment: Frontend verification should include visual/interactive testing, but tool availability is part of the real environment.
- Risk if ignored: We could overclaim visual QA while only testing HTTP resource loading.
- Fix or control: Ran API/resource smoke tests for `/console`, CSS, JS, and auth flow; marked full Playwright visual verification as pending.
- Verification: HTTP smoke passed; visual verification remains open.
- Interview version: I distinguished API-level smoke from full UI verification instead of pretending they are equivalent.

## PowerShell HTTP Smoke Checks Need Care

- Date: 2026-06-09
- Version: V1.0
- Type: pitfall
- Context: We used PowerShell to manually verify Refresh Token cookie behavior against the running API.
- What happened: `Invoke-WebRequest` on Windows PowerShell required `-UseBasicParsing`, and reading cookies from the session container was misleading because the refresh cookie is scoped to `/auth`.
- Engineering judgment: Smoke-test tooling can lie or obscure behavior; verify security-sensitive behavior through direct response headers and database state, not a single client abstraction.
- Risk if ignored: We could falsely conclude Refresh Token Rotation was broken or working based on a client-side cookie-container quirk.
- Fix or control: Inspected the `Set-Cookie` headers directly and confirmed `/auth/refresh` returns a new refresh token value.
- Verification: Login and refresh responses both returned `Set-Cookie`; the token values differed and included `HttpOnly`.
- Interview version: I learned to validate auth behavior at the HTTP protocol level, not just through a convenience client.

## RAG Generation Can Hide Retrieval Problems

- Date: 2026-06-11
- Version: V3.0
- Type: pitfall
- Context: V3 connects retrieval results to a chat model.
- What happened: A naive RAG endpoint could simply send the user question to the model and return fluent text.
- Engineering judgment: Fluent text is not the same as an auditable enterprise answer. The API must return sources, confidence, gaps, and next steps.
- Risk if ignored: The system could look impressive while failing the core consulting requirement: users cannot tell what evidence supported the answer.
- Fix or control: V3 validates structured JSON from the chat provider and always returns citations separately from the generated answer.
- Verification: Tests assert citation fields, retrieval method, group isolation, and clear provider-key failure.
- Interview version: I treated RAG as an evidence pipeline, not just a chat completion wrapper.

## Small ECS Deployment Needs Network And Memory Controls

- Date: 2026-06-11
- Version: V3.2
- Type: pitfall
- Context: The project was deployed to a 2C2G Alibaba Cloud ECS instance.
- What happened: The server had no swap, Docker Hub image pulls timed out, and Docker build stalled while downloading Python dependencies from default PyPI.
- Engineering judgment: Cloud deployment failures are often infrastructure and network path issues, not application bugs.
- Risk if ignored: The team might chase code problems while the actual blocker is registry access, package mirrors, or insufficient memory headroom.
- Fix or control: Added 2 GiB swap, configured Docker registry mirrors, and changed Dockerfile pip installs to use the Aliyun PyPI mirror.
- Verification: Docker Compose eventually started healthy API and PostgreSQL containers, and `/docs` became reachable publicly.
- Interview version: I debugged deployment by separating app, container, registry, package download, and server resource layers.

## Default Security Group Was Too Open

- Date: 2026-06-11
- Version: V3.2
- Type: pitfall
- Context: The ECS security group initially had broad inbound access.
- What happened: Inbound rules allowed `TCP 1/65535` from `0.0.0.0/0`, plus an unnecessary RDP `3389` rule.
- Engineering judgment: A deployment is not complete when the app starts; the network boundary must also be reduced to the required ports.
- Risk if ignored: Any exposed service on the instance could be reachable from the public internet.
- Fix or control: Removed broad TCP and RDP rules, kept SSH restricted to the user's public IP, and left only temporary demo access for port `8000`.
- Verification: Swagger remained reachable after cleanup, and server access still worked.
- Interview version: I treated security group cleanup as part of the cloud delivery checklist, not a later nice-to-have.

## RAG Logs Are Sensitive Data

- Date: 2026-06-11
- Version: V3.3
- Type: pitfall
- Context: V3.3 added persisted RAG run history.
- What happened: It would be easy to treat RAG history as ordinary debug logs.
- Engineering judgment: A RAG run can contain user questions, generated consulting advice, and snippets from internal knowledge, so it must follow the same group boundary as documents.
- Risk if ignored: A history endpoint could leak sensitive questions and cited source material even if live retrieval is protected.
- Fix or control: Run list and detail endpoints require membership and filter by `group_id`.
- Verification: Tests prove non-members cannot read run history.
- Interview version: I recognized that observability data can itself become protected business data.

## Upload Cleanup Is Part Of Upload Correctness

- Date: 2026-06-11
- Version: V2.2
- Type: pitfall
- Context: V2.2 chunked upload wrote temp chunks and merged files but never cleaned them.
- What happened: Three cleanup gaps: temp chunks survived successful complete, hash-mismatch merged files became orphans in document-storage, and parser-failure merged files also leaked.
- Engineering judgment: Upload is not complete when the document is ingested; it is complete when the temporary artifacts are gone and the permanent storage contains only valid files.
- Risk if ignored: `upload-tmp` grows without bound; `document-storage` accumulates invalid files that could be mistaken for valid originals; on a small 2 GiB ECS the leaked disk compounds with concurrent uploads.
- Fix or control: Added `cleanup_upload_temp_dir` and `cleanup_merged_file` helpers; integrated them into the success, hash-mismatch, and parser-failure paths in `complete_document_upload`.
- Verification: 4 new tests pass: cleanup after success (temp gone, merged kept), cleanup after hash mismatch (both gone), cleanup after parser failure (both gone), and member GET upload session now returns 403.
- Interview version: I treated upload cleanup as part of the ingestion contract, not a later nice-to-have. Every temporary file path has a corresponding deletion path.

## Upload Session Visibility Was Broader Than Write Permission

- Date: 2026-06-11
- Version: V2.2
- Type: pitfall
- Context: The three-stage upload protocol requires Owner/Admin for init, chunk, and complete, but session status lookup was open to any group member.
- What happened: `GET /uploads/{upload_id}` used `get_membership_or_404` (any member) while all other upload endpoints used `require_group_role(..., {"owner", "admin"})`.
- Engineering judgment: Read access to upload metadata (file hash, chunk progress, file size) is not harmless — it exposes ingestion intent and content identity before the document is ready. The permission surface should be uniform.
- Risk if ignored: A member could enumerate upload sessions, learn file hashes and names before documents are published, or use metadata to infer document content through hash comparison.
- Fix or control: Changed `get_document_upload_session` from `get_membership_or_404` to `require_group_role(db, current_user.id, group_id, {"owner", "admin"})`.
- Verification: `test_member_cannot_get_upload_session` proves member GET returns 403.
- Interview version: I aligned read and write permissions on the upload session resource so the security boundary is consistent, not asymmetric.

## Full-File Hash Verification Can Be A Memory Bottleneck

- Date: 2026-06-11
- Version: V2.2
- Type: pitfall
- Context: `complete_document_upload` used `storage_path.read_bytes()` to load the entire merged file into RAM for hash verification.
- What happened: On a 2 GiB ECS running API + PostgreSQL + pgvector, two concurrent 50 MiB uploads would consume ~100 MB just for hash verification, competing with the database and embedding rebuild.
- Engineering judgment: Hash verification should be O(1) in memory, not O(file_size). The file only needs to be fully loaded if the hash passes and parsing is required.
- Risk if ignored: Concurrent uploads could trigger OOM kills on a small production server, making upload reliability dependent on traffic luck.
- Fix or control: Added `verify_file_hash()` in `document_files.py` — streams the file in 64 KB chunks through `hashlib.sha256.update()`. The `complete` endpoint now calls `verify_file_hash()` first; if hash fails, the file is never fully loaded. Only after hash verification passes does `read_bytes()` load for parsing.
- Verification: `test_upload_temp_and_merged_cleaned_after_hash_mismatch` covers the hash-mismatch path; existing chunked upload tests still pass with streaming verification.
- Interview version: I replaced a memory-proportional hash check with a constant-memory streaming check so that upload reliability does not depend on how many uploads happen to be running at once.

## Bigger Upload Limit Is Not Large File Support

- Date: 2026-06-11
- Version: V2.2
- Type: pitfall
- Context: The project needed to handle larger enterprise documents.
- What happened: Simply increasing the upload size would still make interrupted uploads restart from zero and would not solve duplicate ingestion.
- Engineering judgment: Large upload support needs resumability, idempotency, and integrity checks.
- Risk if ignored: Users could waste bandwidth, create duplicate documents, or get corrupted files into the retrieval index.
- Fix or control: Added `init -> chunks -> complete`, group-scoped file hash checks, chunk upsert, and final SHA-256 validation.
- Verification: Tests cover resume, duplicate chunk upload, incomplete complete, hash mismatch, and instant upload.
- Interview version: I treated large files as a reliability problem, not just a request-size configuration.

## Test Lifespan Must Use The Test Database

- Date: 2026-06-13
- Version: V4/V7 agent iteration
- Type: pitfall
- Context: Agent tests appeared to hang for minutes before any assertion failed.
- What happened: The shared `client` fixture overrode request-time `get_db`, but the FastAPI lifespan startup still used `main.SessionLocal` for orphaned ingestion job recovery. In tests, that startup path could try to connect to the real configured database instead of the temporary SQLite database.
- Engineering judgment: Test isolation must cover the whole application lifecycle, not only endpoint dependencies. Startup recovery, background tasks, and request handlers all need the same test database boundary.
- Risk if ignored: Pytest looks "stuck", CI becomes unreliable, and developers may misdiagnose the issue as slow fixtures or dependency problems.
- Fix or control: Patched `semantic_lighthouse.main.SessionLocal` in `tests/conftest.py` alongside the document router background-task session factory, so lifespan recovery uses the same file-backed SQLite test database.
- Verification: `tests/test_agent.py::test_create_agent_run` dropped from 120s timeout to 0.66s, `tests/test_agent.py` passed in ~7s, and full pytest passed with 106 tests.
- Interview version: I found that the test dependency override did not cover startup lifecycle code, so I made the test database boundary apply to lifespan recovery as well as request handlers.

## Docker CE Image Does Not Guarantee Docker Socket Access

- Date: 2026-06-16
- Version: Cloud Deployment
- Type: pitfall
- Context: Tencent Cloud Lighthouse was created from an Ubuntu Server 24.04 Docker CE image, so Docker and Compose were already installed.
- What happened: Running `docker compose` as the `ubuntu` user failed with `permission denied while trying to connect to the Docker daemon socket`.
- Engineering judgment: Installed tooling and user permissions are separate deployment checks. A Docker image can have the daemon installed while the login user still lacks socket access.
- Risk if ignored: Deployment can stall on a permissions error even though Docker is correctly installed, leading to unnecessary package reinstall attempts.
- Fix or control: Use `sudo docker compose` for initial deployment, or run `sudo usermod -aG docker ubuntu` and re-login before using Docker without `sudo`.
- Verification: `sudo docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build` started both production containers successfully.
- Interview version: I separated environment readiness from user permission readiness; the fix was not reinstalling Docker, but using the correct privilege boundary.
