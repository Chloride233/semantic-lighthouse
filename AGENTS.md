# Semantic Lighthouse Agent Instructions

These instructions apply to `F:\semantic-lighthouse`.

@import docs/project-status.toml
@import docs/development-workflow.md

When your agent runner leaves `@import` as literal text, open the imported files before editing.

## Operating Frame

- Product identity: Semantic Lighthouse is an ontology-oriented semantic operating layer workspace for enterprise AI transformation.
- "Ontology" here means business objects, properties, relationships, actions, permissions, evidence, and Agent-facing interfaces.
- Current state, next gate, MCP status, frontend status, and latest verified counts live in `docs/project-status.toml`.
- The delivery chain is: auth and group isolation -> document ingestion -> retrieval evidence -> citation-grounded RAG -> user-confirmed task/action -> controlled Agent workflow -> Ontology governance and graph -> semantic operating layer.
- RAG and Agent features support the Ontology direction; the product boundary is the semantic operating layer.

## Session Start

1. Read `docs/project-status.toml`.
2. Read `docs/development-workflow.md`.
3. Run `git status --short`.
4. Run `git log --oneline -5`.
5. Declare the lane before editing: `Lane: Fast / Standard / Safety` plus one sentence.

Load additional context only when the task matches:

- Product or roadmap: `PRODUCT.md`, `docs/product-alignment-prd.md`, `docs/project-roadmap.md`.
- Phase closeout or handoff: `docs/agent-handoff.md` and the relevant latest engineering-memory entry.
- Architecture, call-chain, route, symbol, or impact analysis: use `codebase-memory-mcp` first when available; project name is `F-semantic-lighthouse`.
- Backend/API/auth/group isolation/migrations/RAG/Ontology: relevant `src/`, `tests/`, `alembic/`, and phase docs.
- Frontend: relevant `static/js/`, `static/styles.css`, `docs/frontend-f2-planning.md`, and `docs/frontend-redesign-plan.md`.
- Deployment/cloud: `docs/cloud-smoke-playbook.md`, `docs/deployment-v3-cloud.md`, Docker files, and deployment scripts.
- Enterprise AI transformation, Ontology, RAG, Agent, Palantir, vendors, or methodology: inspect `F:\ontology-kb\knowledge-graph\INDEX.md` and `schema.md`.

## Architecture Invariants

- Derive `group_id` from authenticated server-side context for documents, chunks, retrieval, RAG, conversations, tasks, action suggestions, Agent runs, ontology objects, model packages, projects, datasets, bindings, outcomes, and evidence links.
- Agent behavior is a controlled coordination layer. Backend services own permission checks, status transitions, hash checks, CRUD, and audit writes.
- Write-like Agent/action behavior includes role authorization, server-side group scope, audit/provenance, and user confirmation before the write.
- MCP is a future Agent-facing adapter candidate. Runtime MCP work starts only after a dedicated Safety Lane phase approves scope, SDK/dependency, identity, group authorization, audit, provenance, and HITL boundaries.
- Runtime data exposure stays bounded: provenance can explain source objects, while storage paths, raw secrets, and unreviewed external data stay out of responses and artifacts.
- Phase 19 offline ontology artifacts represent JSON/markdown output scope only; DB-backed governance feedback and AdventureWorks support require separate delivery records.

## Local Commands

Use PowerShell from the repo root.

```powershell
# Install/update local environment
.\.venv\Scripts\python -m pip install -r requirements.txt -r requirements-dev.txt
.\.venv\Scripts\python -m pip install -e .

# Related tests for Standard Lane
.\.venv\Scripts\python -m pytest tests\test_specific.py -p no:cacheprovider

# Full regression for Safety Lane or phase boundary
.\.venv\Scripts\python -m pytest -p no:cacheprovider --basetemp=.tmp\pytest-agent

# UI smoke after UI code changes
.\.venv\Scripts\python scripts\verify_ui.py

# Lint
.\.venv\Scripts\python -m ruff check src tests

# Markdown/doc boundary check
.\.venv\Scripts\python scripts\check_doc_alignment.py

# Whitespace and status closure
git diff --check
git status --short
```

SQLite migration smoke uses a temporary DB:

```powershell
$dbPath = "F:\semantic-lighthouse\.tmp\migration-smoke.db"
New-Item -ItemType Directory -Force -Path "F:\semantic-lighthouse\.tmp" | Out-Null
if (Test-Path $dbPath) { Remove-Item $dbPath -Force }
$env:DATABASE_URL = "sqlite+pysqlite:///" + $dbPath.Replace("\\","/").Replace("\","/")
.\.venv\Scripts\python -m alembic upgrade head
.\.venv\Scripts\python -m alembic current
```

## Environment

- Python runtime target is `>=3.14` from `pyproject.toml`.
- Local default DB is PostgreSQL from `.env.example`; SQLite is valid for tests and smoke scripts that create temporary DBs.
- `JWT_SECRET_KEY` must be at least 32 bytes for local app runs.
- Fake-provider smoke uses `EMBEDDING_PROVIDER=fake`, `CHAT_PROVIDER=fake`, `EMBEDDING_MODEL=fake`, `CHAT_MODEL=fake`, and `EMBEDDING_DIMENSION=8`.
- Real embedding/chat runs require provider keys such as `DASHSCOPE_API_KEY` or `DEEPSEEK_API_KEY`.
- Knowledge-base default path is `F:\ontology-kb\knowledge-graph`.
- Runtime storage paths include `document-storage`, `upload-tmp`, and `dataset-storage`; keep them out of commits.

## Frontend Work

- Frontend F2 is complete; future UI work is incremental and lane-scoped.
- Visual direction is Minimalism & Swiss Style with Semantic Lighthouse color semantics.
- After frontend code changes, run `scripts\verify_ui.py` and Playwright checks for the touched flow or viewport.
- Keep legacy console routes working for every UI task; retiring a route requires explicit task scope.

## Git And Review

- Use branch names `codex/<short-topic>` for agent-created branches.
- Use one focused commit per implementation slice.
- Use conventional commit prefixes: `feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `chore:`.
- Stage only files owned by the current task.
- Keep secrets, `.env*` except examples, `*.db`, `.venv/`, `.claude/`, caches, logs, build artifacts, and runtime storage out of Git.
- PR description format:
  - Summary
  - Verification
  - Risk / rollback
  - Docs or status updates

## Closure

End each implementation or review handoff with:

```text
Scope completed:
Boundaries preserved:
Verification run:
Diff risk:
Docs/status:
Commit:
```

Fast Lane ends with `git diff --check`, `git status --short`, and a commit. Standard and Safety Lane closure follows `docs/development-workflow.md`.
