# Semantic Lighthouse Agent Instructions

These instructions apply to the `F:\semantic-lighthouse` repository.

## Project Identity

Semantic Lighthouse / 语义灯塔 is an ontology-oriented semantic operating layer workspace for enterprise AI transformation. It helps enterprises turn fragmented knowledge, documents, systems, and workflows into a permission-aware, auditable, actionable Ontology semantic layer that can be safely used by applications and Agent workflows.

In this project, Ontology means the enterprise semantic operating layer: business objects, properties, relationships, actions, permissions, evidence, and Agent-facing interfaces. It is not just a database schema, not just a knowledge graph, and not just a RAG document library.

Trusted RAG, citations, confidence, knowledge gaps, tasks, and controlled Agent orchestration are the current foundation. They should support the Ontology direction, not replace it. Agent is only a controlled coordination layer for multi-step, tool-based, auditable workflows. The project should prove engineering judgment, not accumulate unexplained frameworks.

Core chain:

```text
auth and group isolation -> document ingestion -> retrieval evidence -> citation-grounded RAG -> user-confirmed task/action -> controlled Agent workflow -> Ontology governance and graph -> semantic operating layer
```

## Context Routing For New Sessions

Avoid loading every project document by default. Before changing code, read the core context first:

1. `docs/project-status.toml` — canonical current state and next gate.
2. `docs/development-workflow.md` — lane, verification, parallel-session, and self-check rules.
3. `git status --short` and recent `git log --oneline -5` — current worktree and baseline.

Then read task-routed context only as needed:

- Product or roadmap work: `PRODUCT.md`, `docs/product-alignment-prd.md`, `docs/project-roadmap.md`.
- Phase closeout or handoff work: `docs/agent-handoff.md` plus relevant latest engineering-memory entries.
- Architecture, call-chain, or impact analysis: use `codebase-memory-mcp` first when available, then inspect relevant files.
- Backend/API/auth/group isolation/migrations/RAG/ontology work: relevant `src/`, `tests/`, `alembic/`, and phase docs.
- Frontend work: relevant `static/js/`, `static/styles.css`, and frontend planning docs only.
- Deployment/cloud work: `docs/cloud-smoke-playbook.md` and deployment files.

Do not read the full roadmap, handoff history, or engineering memory for a small Fast Lane change unless the task specifically needs it.

## Working Rules

- Review and test before editing.
- Keep changes surgical and directly tied to the requested goal.
- Prefer the simplest implementation that closes a verified risk.
- Do not introduce speculative abstractions or unexplained enterprise patterns.
- Keep `group_id` isolation as a hard invariant across documents, chunks, retrieval, RAG, conversations, tasks, action suggestions, and Agent runs.
- Do not use Agent behavior to replace deterministic backend logic.
- Agent or task write behavior must be permission-checked, group-scoped, auditable, and user-confirmed.
- Do not let new work drift back into "generic RAG app" or "generic Agent platform" framing. If a feature touches product direction, explain how it supports the Ontology semantic operating layer.
- Treat MCP as a future Agent-facing adapter only. Do not add MCP runtime, SDK dependencies, resources, or tools. Future MCP work must reuse server-side identity, group authorization, audit, bounded provenance, and backend HITL; never trust model/client-supplied `group_id` as authority. See `docs/project-status.toml` for current MCP status.
- Frontend F2 is complete. Current project state is in `docs/project-status.toml`.
- Every meaningful change must update project memory and be committed to Git.
- Do not commit secrets, tokens, cookies, database files, runtime storage, `.venv/`, or `.claude/`.

## Development Code Graph Tool

This project may use `codebase-memory-mcp` as a developer-only code exploration tool.

- Project name: `F-semantic-lighthouse`.
- When exploring architecture, symbols, call graphs, impact analysis, routes, or code snippets, prefer `codebase-memory-mcp` tools first: `list_projects`, `get_architecture`, `search_graph`, `trace_path`, `get_code_snippet`, and `search_code`.
- Use `rg` for plain text search, exact string search, non-code files, or when `codebase-memory-mcp` is unavailable.
- This does not change the product MCP moratorium. Do not add MCP runtime, SDK dependencies, resources, tools, or server/client code to Semantic Lighthouse unless a separate Safety Lane phase explicitly approves runtime MCP work.

## Shared Knowledge Base

The persistent enterprise AI transformation knowledge base lives at:

```text
F:\ontology-kb\knowledge-graph
```

When work touches enterprise AI transformation, Ontology, RAG, Agent, Palantir Foundry, vendors, or methodology topics, inspect this knowledge base first. The files are Obsidian-compatible Markdown with YAML frontmatter.

Important entry points:

- `F:\ontology-kb\knowledge-graph\INDEX.md`
- `F:\ontology-kb\knowledge-graph\schema.md`

## Development Workflow — Tiered Iteration

Every development task MUST reference `docs/development-workflow.md`. The project uses three risk-based lanes:

- **Fast Lane** — docs, prompts, minor UI copy/CSS, non-core test fixes, comment/README tweaks
- **Standard Lane** — normal backend/frontend features, non-permission logic, non-breaking API changes, routine tests
- **Safety Lane** — auth, permissions, group_id isolation, Agent writes, RAG citation/confidence, document lifecycle, production config, migrations, security audit, deployment-affecting changes

### Lane Declaration

At the start of every iteration, declare the lane before touching code:

```
Lane: Fast / Standard / Safety
Reason: <one sentence>
```

The lane determines verification depth and documentation burden. See `docs/development-workflow.md` for the full table.

### Over-Execution Prohibitions

- Do NOT write a long plan for Fast Lane.
- Do NOT run full `pytest` on Fast Lane.
- Do NOT update all entry-point docs for small changes.
- Do NOT use `python -c`, heredoc, or Bash to generate large code blocks to work around tool restrictions.
- Do NOT cargo-cult Safety Lane checklist into Fast or Standard work.

## Verification Commands

Default local checks (use according to lane, not blindly):

```powershell
# Related tests only (Standard Lane)
.\.venv\Scripts\python -m pytest tests/test_specific.py -p no:cacheprovider

# Full regression (Safety Lane, or Standard phase boundary)
.\.venv\Scripts\python -m pytest -p no:cacheprovider --basetemp=.tmp\pytest-agent

# UI smoke
.\.venv\Scripts\python scripts\verify_ui.py

# Lint (Standard: changed files only; Safety: full src tests)
.\.venv\Scripts\python -m ruff check src tests
```
