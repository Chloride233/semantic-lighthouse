# Agent Handoff Snapshot

Last updated: 2026-06-21 (Phase 15 closeout)

## State Source

**Canonical project state**: `docs/project-status.toml` — always read this first.
Detailed delivery history: `docs/archive/agent-handoff-through-phase14.md`.
This handoff is operational context, not the canonical phase tracker. If the baseline below conflicts with `docs/project-status.toml` or `git log`, treat it as historical and follow `docs/project-status.toml`.

## Latest Baseline

| Item | Value |
|------|-------|
| Commit | `b52e037` |
| Backend pytest (non-E2E) | 873 collected; Phase 15 related all pass |
| ruff | clean |
| Migration | `0026` at head |
| verify_ui | 53/53 |
| E2E | 18/18 |
| Phase 15.3 evidence-draft tests | 22 pass |
| Phase 15.3 evidence regression | 35 evidence + 29 drafts = 64 pass |
| Phase 15.1–15.2 (existing) | no regressions in related suites |

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
| Backend (non-E2E grouped) | 848 passed, 3 skipped | All 851 collected non-E2E tests covered by grouped runs after single-command timeout |
| Project evidence | 38 passed | permissions, dual isolation, lifecycle, provenance, audit atomicity |
| S2.3A related | 95 passed | Conversations, Tasks, Agent, project context; migration 0025 roundtrip |
| S2.3B focused | 16 passed | Project-bound retrieval, tool scope, empty evidence, archive denial |
| S2.3B related | 100 passed | Retrieval, Conversations, Agent, project work context |
| S2.3B grouped non-E2E | Passed | One-shot full command timed out after about 10 minutes; grouped suites covered all 832 collected non-E2E tests and passed |
| S2.4B focused | 65 passed | Project summary endpoint, permissions, active evidence, safe provenance, scoped counts |
| S2.4C focused | 48 passed | Project-bounded RAG, RagRun.project_id, no fallback, no auto evidence link |
| S2.4C related | 139 passed | RAG, retrieval, project evidence, project context, bounded retrieval |
| S2.4C grouped non-E2E | 848 passed, 3 skipped | One-shot full command timed out after about 10 minutes; grouped suites covered all 851 collected non-E2E tests |
| verify_ui | 47/47 | Real owner full chain F2A+F2B, all assertions pass |
| E2E (Playwright) | 18/18 | F2A, F2B (owner/member/WARN/FAIL/isolation), F2C (responsive/a11y) |
| Screenshots | 6 files | `.tmp/f2c/`, 32–97 KB, stage-verified, 0 console errors |

## Next Decision Gate

**Implement Phase 16.1 or review plan**: Phase 16 is planned — Pilot Outcome & FDE Delivery Record v1. See `docs/phase16-planning.md`. The plan defines four slices to turn the completed Pilot chain into a durable, auditable delivery record. Next decision: implement Slice 16.1 (outcome record design/schema), review the full plan with project owner, or adjust scope based on interview/portfolio feedback.

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
