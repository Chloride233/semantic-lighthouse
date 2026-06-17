# Semantic Lighthouse Agent Instructions

These instructions apply to the `F:\semantic-lighthouse` repository.

## Project Identity

Semantic Lighthouse / 语义灯塔 is a permission-aware knowledge evidence workspace for enterprise AI transformation. It uses trusted RAG to turn group-scoped knowledge into evidence-backed answers, confidence judgments, knowledge gaps, and user-confirmed action items. Agent is only a controlled coordination layer for multi-step, tool-based, auditable workflows. The project should prove engineering judgment, not accumulate unexplained frameworks.

Core chain:

```text
auth and group isolation -> document ingestion -> retrieval -> citation-grounded RAG -> audit -> confirmed action/task -> controlled Agent workflow
```

## Required Reading For New Sessions

Before changing code, read:

1. `PRODUCT.md`
2. `docs/product-alignment-prd.md`
3. `CLAUDE.md`
4. `README.md`
5. `docs/agent-handoff.md`
6. `docs/project-roadmap.md`
7. `docs/engineering-memory/README.md`
8. Latest entries in `docs/engineering-memory/highlight-log.md` and `pitfall-log.md`

## Working Rules

- Review and test before editing.
- Keep changes surgical and directly tied to the requested goal.
- Prefer the simplest implementation that closes a verified risk.
- Do not introduce speculative abstractions or unexplained enterprise patterns.
- Keep `group_id` isolation as a hard invariant across documents, chunks, retrieval, RAG, conversations, tasks, action suggestions, and Agent runs.
- Do not use Agent behavior to replace deterministic backend logic.
- Agent or task write behavior must be permission-checked, group-scoped, auditable, and user-confirmed.
- Every meaningful change must update project memory and be committed to Git.
- Do not commit secrets, tokens, cookies, database files, runtime storage, `.venv/`, or `.claude/`.

## Shared Knowledge Base

The persistent enterprise AI transformation knowledge base lives at:

```text
F:\ontology-kb\knowledge-graph
```

When work touches enterprise AI transformation, Ontology, RAG, Agent, Palantir Foundry, vendors, or methodology topics, inspect this knowledge base first. The files are Obsidian-compatible Markdown with YAML frontmatter.

Important entry points:

- `F:\ontology-kb\knowledge-graph\INDEX.md`
- `F:\ontology-kb\knowledge-graph\schema.md`

## Verification Expectations

Default local checks:

```powershell
.\.venv\Scripts\python -m pytest -p no:cacheprovider --basetemp=.tmp\pytest-agent
.\.venv\Scripts\python scripts\verify_ui.py
```

Use narrower tests first when iterating, then run the broader gate before committing meaningful backend or frontend changes.
