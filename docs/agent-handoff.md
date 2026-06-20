# Agent Handoff Snapshot

Last updated: 2026-06-20 (S2.4B delivered and reviewed, migration 0025)

## State Source

**Canonical project state**: `docs/project-status.toml` — always read this first.
Detailed delivery history: `docs/archive/agent-handoff-through-phase14.md`.

## Latest Baseline

| Item | Value |
|------|-------|
| Commit | `ab99b9d` |
| Backend pytest | 786 passed |
| ruff | clean |
| Migration | `0025` at head |
| verify_ui | 47/47 |
| E2E | 18/18 |
| Screenshots | `.tmp/f2c/` 6 files |
| Evidence tests | 38 pass |
| S2.3A related tests | 95 pass |
| S2.3B focused tests | 16 pass |
| S2.3B related regression | 100 pass |
| S2.3B grouped non-E2E regression | passed across all 832 collected non-E2E tests |
| S2.4B focused tests | 65 pass |

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
| Backend (non-E2E baseline) | 786 passed, 3 skipped | Last one-shot baseline before S2.3 |
| Project evidence | 38 passed | permissions, dual isolation, lifecycle, provenance, audit atomicity |
| S2.3A related | 95 passed | Conversations, Tasks, Agent, project context; migration 0025 roundtrip |
| S2.3B focused | 16 passed | Project-bound retrieval, tool scope, empty evidence, archive denial |
| S2.3B related | 100 passed | Retrieval, Conversations, Agent, project work context |
| S2.3B grouped non-E2E | Passed | One-shot full command timed out after about 10 minutes; grouped suites covered all 832 collected non-E2E tests and passed |
| S2.4B focused | 65 passed | Project summary endpoint, permissions, active evidence, safe provenance, scoped counts |
| verify_ui | 47/47 | Real owner full chain F2A+F2B, all assertions pass |
| E2E (Playwright) | 18/18 | F2A, F2B (owner/member/WARN/FAIL/isolation), F2C (responsive/a11y) |
| Screenshots | 6 files | `.tmp/f2c/`, 32–97 KB, stage-verified, 0 console errors |

## Next Decision Gate

**Approve S2.4C project-bounded RAG endpoint design**: S2.4B delivered `GET /groups/{gid}/projects/{pid}/summary` as a read-only aggregation endpoint for future Pilot overview panels. Next design question: whether and how to add `POST /groups/{gid}/projects/{pid}/rag/answer` so Pilot Ask retrieves only active project evidence while existing group-scoped Ask remains compatible.

## Key API Surfaces

- `POST /auth/register`, `/auth/login`, `/auth/refresh`, `/auth/logout`, `GET /auth/me`
- `POST /groups`, `GET /groups`, `POST /groups/{gid}/invites`, `POST /groups/join-by-invite`
- `POST /groups/{gid}/documents/import-local`, `/upload`, `/uploads/init|chunks|complete`
- `GET /groups/{gid}/documents/search`, `/semantic-search`
- `POST /groups/{gid}/rag/answer`, `GET /rag/runs`, `GET /rag/runs/{run_id}`
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
