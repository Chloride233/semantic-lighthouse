# Agent Handoff Snapshot

Last updated: 2026-06-22 (frontend visual closeout accepted)

## State Source

**Canonical project state**: `docs/project-status.toml` — always read this first.
Detailed delivery history: `docs/archive/agent-handoff-through-phase14.md`.
This handoff is operational context, not the canonical phase tracker. If the baseline below conflicts with `docs/project-status.toml` or `git log`, treat it as historical and follow `docs/project-status.toml`.

## Latest Baseline

| Item | Value |
|------|-------|
| Commit | `58620bc` (16.1), `b5f6877` (16.2) |
| Phase 16.4 delivery commit | `d884813` |
| Backend pytest | Phase 16.1–16.2–16.4: 66/66 pass |
| ruff | clean (changed files only) |
| Migration | `0027` at head |
| Phase 16.1 outcome CRUD tests | 40 pass |
| Phase 16.2 outcome-summary tests | 13 pass |
| Phase 16.4 markdown artifact tests | 13 pass (66 total) |

## Architecture Boundaries

- **Auth**: JWT access token (15min) + httpOnly refresh cookie + rotation + replay detection. BCrypt passwords. Owner/Admin/Member roles per group.
- **Group isolation**: `group_id` enforced at DB query level on all multi-tenant resources — documents, chunks, RAG runs, conversations, tasks, Agent runs, ontology entities/relations/issues, modeling drafts, packages, projects, datasets, bindings, and project evidence links. Conversations, Tasks, and Agent runs now support immutable optional `project_id`, validated against the route group. Never trust client-supplied scope alone.
- **Agent**: Controlled coordination layer only. Deterministic backend logic (permissions, status filters, hash checks, CRUD) must not be replaced by LLM decisions. All Agent write actions require role authorization, `group_id` isolation, and user confirmation (HITL).
- **MCP**: Not started. Future candidate only — requires dedicated Safety Lane plan. See `docs/mcp-agent-boundary-design.md`.
- **Frontend**: F2 complete. Vanilla JS ES modules + hash router. Zero npm dependencies. Old pages preserved in "更多工具" dropdown.
- **No-write invariants**: MCP, Action execution, data write-back, Graph RAG — none implemented.

## Current Risks

- PDF parsing: extractable text only, no OCR.
- DOCX parsing: ordinary paragraphs only, no tables/headers/footers.
- Token usage / latency / cost not tracked in rag_runs or conversation_messages.
- No max concurrent upload session limit.
- `read_bytes()` on final parse — fine for 50 MiB, monitor on 2 GiB ECS.
- Ontology KB governance drift: `INDEX.md` / `AUTO_INDEX.md` reference `research/...` which may not exist.
- Eval drift: `docs/eval/rag-queries-ontology.json` contains expected doc IDs that do not exist in the KB.
- Bound dataset files moved/deleted on disk → query returns 422 (not silent).
- Concurrent binding generation may produce IntegrityError — handled by unique constraint.
- No caching layer — repeated queries re-read files.
- `test_conversations.py` blocked by Windows temp dir PermissionError (19 tests, pre-existing).
- `test_upload_then_ask_with_answer_card` uses forced menu-open via JS evaluation (timing workaround).

## Verification Summary

| Suite | Count | Notes |
|-------|-------|-------|
| Phase 16.1 outcomes CRUD | 40 passed | Permissions, evidence/package validation, query_refs privacy, cross-group isolation, list/read. |
| Phase 16.2 outcome-summary | 13 passed | Member read, outsider 403, cross-group 404, null-latest, uses-latest, evidence/package/runtime counts. |
| Phase 16.4 markdown artifact | 13 passed | Member read, content checks, forbidden keys, no side effects, JSON endpoint unchanged. |
| Ruff (changed files) | clean | projects.py, outcomes.py, schemas.py, test_pilot_outcomes.py |
| Migration smoke | 0027 at head | No new migration for 16.2/16.4; 0027 still at head. |
| Closeout review (2026-06-21) | PASS | All gates below checked and passed. |
| Doc alignment | PASS | 7 entry docs checked, no stale expressions |

## Phase 16 Closeout Review

**Review date**: 2026-06-21. **Reviewer**: automated closeout pass.

| Gate | Status | Detail |
|------|--------|--------|
| Permissions | ✅ | POST outcomes: owner/admin via `require_group_role`. GET outcomes/outcome-summary/outcome-artifact.md: member+ via `get_membership_or_404`. |
| Group isolation | ✅ | All queries filter `.group_id == group_id`; `_get_project_or_404` rejects cross-group. |
| Project isolation | ✅ | Evidence links validated for same project; packages validated for same project if scoped; outcome list/get queries filter `.project_id == project_id`. |
| GET side-effect-free | ✅ | `get_outcome_summary`, `get_outcome_artifact`, `list_outcomes`, `get_outcome` — all read-only, no db.add/commit. |
| Privacy | ✅ | Evidence refs: bounded `_build_provenance` (no raw_content/paths). Package refs: id/version/hash/status/count only. Query refs: recursive `_validate_query_refs_safe`. Markdown: provenance note sanitized. Artifact/summary responses contain no raw data, paths, secrets, or stack traces. |
| Sorting stability | ✅ | Latest outcome: `created_at.desc(), id.desc()`. Latest package: `created_at.desc(), id.desc()`. Latest runtime: `created_at.desc(), id.desc()`. All have stable tiebreakers. |
| No migration drift | ✅ | Only migration is 0027 (pilot_outcome_records from 16.1). No additional migrations for 16.2/16.4. |
| Test coverage | ✅ | 66 tests: 40 CRUD + 13 summary + 13 artifact. All pass. |
| Doc alignment | ✅ | `check_doc_alignment.py` PASS. `project-status.toml` latest_commit = `abb1149`. |

## Phase 17 Closeout Review

**Review date**: 2026-06-21. **Reviewer**: automated closeout pass.

| Gate | Status | Detail |
|------|--------|--------|
| Smoke script | ✅ PASS | `scripts/smoke_fde_demo.py` — 11/11 steps, 0.84s, artifact gate PASS (0 findings) |
| Seed scenario | ✅ Complete | Manufacturing equipment reliability, 4 object types, 12-column CSV spec, synthetic data only |
| Artifact quality gate | ✅ PASS | 7 required sections, 11 forbidden terms, 5 boundedness rules — 0 violations on smoke output |
| Interview script | ✅ Refreshed | `docs/interview-demo-questions.md` — FDE narrative, 5-min demo script, 5 FAQ items |
| Docs aligned | ✅ PASS | `check_doc_alignment.py` PASS, 7 entry docs |
| No code regressions | ✅ N/A | No product code changed in Phase 17 (scripts only) |
| Migration drift | ✅ Expected | `migration_head` = `0028` after Alembic version table length fix |

## Phase 18 Closeout Review

**Review date**: 2026-06-21. **Reviewer**: automated closeout pass.

| Gate | Status | Detail |
|------|--------|--------|
| Config audit | ✅ | 11 items: 8 PASS, 3 FIXED |
| PostgreSQL migration smoke | ✅ | 28/28 on pgvector/pgvector:pg17, `0028 (head)`, rerun in closeout |
| HTTP API smoke | ✅ | 9/9 PASS, ~3.4s, local uvicorn + real HTTP |
| Base-url adapter | ✅ | `--base-url` mode CLI verified |
| Artifact quality gate | ✅ | Inline in smoke_http_api |
| Docs aligned | ✅ | `check_doc_alignment.py` PASS |
| Migration drift | ✅ | `0028` at head (new migration for VARCHAR(64) fix) |
| No regressions | ✅ | Only `alembic/env.py` changed |

## Frontend Policy Realignment (2026-06-21)

The previous "frontend freeze" / "deferred to Kimi" policy has been **retired**. The new policy:
- Frontend work can re-enter future planning.
- UI/UX standard: `ui-ux-pro-max-skill` with **Minimalism & Swiss Style**.
- All future UI changes must follow lane-based verification: `verify_ui` and Playwright when code changes.
- No uncontrolled redesign or framework rewrite.
- Historical "Kimi" / "frontend freeze" references in active docs have been updated with policy notes. Archive docs retain history.

## Legacy Console Page Polish (2026-06-21)

**Status**: DOM classes wired + verify_ui PASS. `.legacyPage` wrapper added to all 6 legacy pages (Documents, Tasks, Ontology, Agent, Conversations, Groups). `.legacyFilters` with `.taskFilter`/`.docFilters` compatibility on filter bars. `.legacyTable` added to Documents and Conversations tables. `.legacyPage .grid` auto-fill layout for Groups panel grid. 53/53 verify_ui PASS, no `button:not(` selectors, all JS syntax checks pass.

**Screenshot QA update (2026-06-22)**: Added `scripts/screenshots_legacy_polish.py` to capture Documents, Tasks, Ontology, Agent, Conversations, and Groups at desktop and mobile widths. 12/12 screenshots PASS in `.tmp/legacy-polish/`; Documents page title/meta restored after visual review; no horizontal overflow reported.

## Frontend Visual Baseline Refresh (2026-06-21)

**Status**: first-pass visual refresh delivered.

- Scope: `static/styles.css` visual override layer plus `static/console.html` title/skip-link cleanup.
- Reference: Handhold-inspired typography, spacing, quiet cards, pill CTAs, and sparse Swiss layout.
- Standard: `ui-ux-pro-max-skill` Minimalism & Swiss Style. Codex environment did not expose that skill directly, so this implementation followed the documented style manually.
- Boundary: no backend/API/migration changes, no framework rewrite, no business JS rewrite.
- Verification: `scripts/verify_ui.py` 53/53 PASS; `scripts/screenshots_f2b.py` PASS with 6 screenshots in `.tmp/f2c/`; `git diff --check` clean.
- Follow-up for CC: polish remaining legacy pages and detailed component states from the new CSS override layer instead of starting a second visual system.

## Frontend Visual Closeout Review (2026-06-22)

**Status**: accepted for current baseline. Codex reviewed the 12 legacy screenshots generated by `scripts/screenshots_legacy_polish.py` across desktop and mobile. Documents, Tasks, Ontology, Agent, Conversations, and Groups render without blocking layout issues or horizontal overflow. Documents title/meta regression was fixed in `622d9de`. Ontology mobile remains dense and mobile filter stacks are visually heavy, but these are follow-up design opportunities, not closeout blockers.

**Verification**: `scripts/verify_ui.py` 53/53 PASS; `scripts/screenshots_legacy_polish.py` 12/12 PASS; `node --check static/js/pages/documents.js` PASS; `python -m py_compile scripts/screenshots_legacy_polish.py` PASS; no `button:not(` selectors; `git diff --check` clean.

## Next Decision Gate

**Plan Phase 19 or portfolio wrap-up**: Phase 18 complete and frontend visual closeout accepted. Avoid opportunistic legacy-page polish unless a new scoped UI lane is opened. Recommended next options:
- Phase 19: ontology operationalization with real data
- Portfolio wrap-up: final docs refresh, demo video, or cloud deployment
- Separately scoped UI phase only if there is a concrete user-flow problem to solve

## Phase 15 Delivery Summary

### 15.1 — Save Scoped RAG Answer As Project Evidence
- Owner/admin save project RAG answer via existing `POST /groups/{gid}/projects/{pid}/evidence-links`.
- evidence_type=rag_run, evidence_id=run_id. Idempotent via existing duplicate detection.

### 15.2 — Project Evidence Review Surface
- `GET /groups/{gid}/projects/{pid}/summary` surfaces recent evidence (max 5).
- Distinguishes document vs RAG run evidence in goal stage.
- Never exposes raw prompts, raw answers, paths, secrets, or stack traces.

### 15.3 — Evidence-Backed Modeling Draft Candidates
- **Slice A (backend)**: `POST /groups/{gid}/projects/{pid}/evidence-draft` — creates proposed OntologyModelingDraft from active ProjectEvidenceLink records. Derives source_rag_run_id, builds bounded evidence_refs with safe provenance. Full group/project isolation. Idempotent. 22 tests.
- **Slice B (frontend)**: Evidence selection + proposal dialog in Pilot goal stage. Owner/admin only. Checkbox selection → draft_type/name/description form → submit. Controls hidden for members and archived projects. 53/53 UI tests pass.
- **Design**: `docs/phase15.3-design.md` — no new models or migrations needed; existing OntologyModelingDraft schema already supported evidence-backed proposals.

## Key API Surfaces

- `POST /auth/register`, `/auth/login`, `/auth/refresh`, `/auth/logout`, `GET /auth/me`
- `POST /groups`, `GET /groups`, `POST /groups/{gid}/invites`, `POST /groups/join-by-invite`
- `POST /groups/{gid}/documents/import-local`, `/upload`, `/uploads/init|chunks|complete`
- `GET /groups/{gid}/documents/search`, `/semantic-search`
- `POST /groups/{gid}/rag/answer`, `GET /rag/runs`, `GET /rag/runs/{run_id}`
- `POST /groups/{gid}/projects/{pid}/rag/answer`
- `POST /groups/{gid}/conversations`, `GET /conversations`, `POST /conversations/{id}/messages`
- `POST /groups/{gid}/tasks`, `GET /tasks`
- `POST /groups/{gid}/agent/runs`, `GET /agent/runs`, `POST /agent/runs/{id}/execute|respond`
- `POST /groups/{gid}/ontology/scan`, `GET /ontology/entities|relations|issues`
- `POST /groups/{gid}/ontology/drafts`, `GET /drafts`, `POST /drafts/generate|review|review-batch`
- `POST /groups/{gid}/ontology/packages`, `GET /packages`, `GET /packages/{pid}/contract`
- `POST /groups/{gid}/projects`, `GET /projects`, `GET /projects/{pid}`
- `GET /groups/{gid}/projects/{pid}/summary`
- `GET /groups/{gid}/projects/{pid}/outcome-summary`
- `GET /groups/{gid}/projects/{pid}/outcome-artifact.md`
- `POST|GET /groups/{gid}/projects/{pid}/outcomes`, `GET /groups/{gid}/projects/{pid}/outcomes/{outcome_id}`
- `POST|GET /groups/{gid}/projects/{pid}/evidence-links`, `DELETE /groups/{gid}/projects/{pid}/evidence-links/{link_id}`
- `POST /projects/{pid}/datasets`, `GET /datasets`
- `POST /projects/{pid}/model-drafts/generate`, `GET /model-drafts/quality`
- `POST /projects/{pid}/model-drafts/packages`, `GET /packages/{pid}/contract`
- `POST /projects/{pid}/runtime/bindings/generate`, `GET /runtime/bindings`
- `POST /projects/{pid}/runtime/query`, `POST /runtime/activate`

## New Session Rules

1. Read `docs/project-status.toml` first — it is the single source of truth.
2. Declare lane at the start of every iteration (`Lane: Fast / Standard / Safety` with one-line reason).
3. Review and test before editing (depth scales with lane).
4. Keep each iteration independently usable. Prefer smallest change that closes the verified risk.
5. Do not introduce architecture the project owner cannot explain.
6. Do not add speculative abstractions for future versions.
7. Keep group-scoped data isolation as a hard invariant.
8. Do not use Agent behavior to replace deterministic backend logic.
9. Any write-like Agent/action behavior must have role authorization, group_id isolation, and user confirmation.
10. Do not let future work drift into generic RAG or generic Agent framing.
11. MCP moratorium: do not implement MCP runtime. See `docs/project-status.toml`.
12. Do not commit `.env*` (except `.example`), `*.db`, `.venv/`, `.claude/`, `__pycache__/`, build artifacts, or storage volumes.
13. Run `scripts/check_doc_alignment.py` at doc/phase boundaries.
14. Do not rely on chat history. Use `git log -1 --oneline` for the latest verified baseline.

## Quick Verification

```powershell
# Related tests (Standard Lane)
.\.venv\Scripts\python -m pytest tests/test_specific.py -p no:cacheprovider

# Full regression (Safety Lane)
.\.venv\Scripts\python -m pytest -p no:cacheprovider --ignore=tests/e2e --basetemp=.tmp\pytest-run

# Lint
.\.venv\Scripts\python -m ruff check src tests

# Doc alignment
.\.venv\Scripts\python scripts\check_doc_alignment.py

# UI smoke (frontend changes only)
.\.venv\Scripts\python scripts\verify_ui.py
```
