# Semantic Lighthouse Agent Instructions

These instructions apply to the `F:\semantic-lighthouse` repository.

## Project Identity

Semantic Lighthouse / 语义灯塔 is an enterprise permission-aware RAG / Agent prototype for internship and interview demonstration. The project should prove engineering judgment, not accumulate unexplained frameworks.

Core chain:

```text
auth and group isolation -> document ingestion -> retrieval -> citation-grounded RAG -> audit trail -> controlled Agent workflow
```

## Required Reading For New Sessions

Before changing code, read:

1. `PRODUCT.md`
2. `CLAUDE.md`
3. `README.md`
4. `docs/agent-handoff.md`
5. `docs/project-roadmap.md`
6. `docs/engineering-memory/README.md`
7. Latest entries in `docs/engineering-memory/highlight-log.md` and `pitfall-log.md`

## Working Rules

- Review and test before editing.
- Keep changes surgical and directly tied to the requested goal.
- Prefer the simplest implementation that closes a verified risk.
- Do not introduce speculative abstractions or unexplained enterprise patterns.
- Keep `group_id` isolation as a hard invariant across documents, chunks, retrieval, RAG, conversations, and Agent runs.
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
