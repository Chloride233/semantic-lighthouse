# Claude Code Handoff Guide

This is the first file Claude Code should read when taking over Semantic Lighthouse.

## Project Intent

Semantic Lighthouse is an ontology-oriented semantic operating layer workspace for enterprise AI transformation. Its destination is to help enterprises turn fragmented knowledge, documents, systems, and workflows into a permission-aware, auditable, actionable Ontology semantic layer that applications and Agent workflows can safely use.

In this project, Ontology means the enterprise semantic operating layer: business objects, properties, relationships, actions, permissions, evidence, and Agent-facing interfaces. It is not just a database schema, not just a knowledge graph, and not just a RAG document library.

Trusted RAG with traceable evidence, confidence judgment, knowledge gaps, and user-confirmed action handoff is the current foundation. Agent is a controlled coordination layer, not the product's default answer to every problem.

The goal is not to build a productized SaaS. The goal is to prove engineering judgment through a maintainable chain:

```text
auth and group isolation -> document ingestion -> retrieval evidence -> citation-grounded RAG answer -> confirmed action/task -> controlled Agent workflow -> Ontology governance and graph -> semantic operating layer
```

Every feature must be explainable by the project owner in business terms, technical terms, risk terms, and interview terms.

## Required Read Order

Before changing code, read these files in order:

1. `AGENTS.md`
2. `docs/project-status.toml` — canonical project state (single source of truth)
3. `PRODUCT.md`
4. `docs/product-alignment-prd.md`
5. `README.md`
6. `docs/agent-handoff.md`
7. `docs/project-roadmap.md`
8. `docs/engineering-memory/README.md`
9. `docs/engineering-memory/learning-index.md`
10. The most recent retrospective, pitfall log, and highlight log entries
11. `docs/cloud-smoke-playbook.md` when deployment or cloud verification is involved

## Working Rules

- **Declare the lane at the start of every iteration** — `Lane: Fast / Standard / Safety` with a one-line reason. See `docs/development-workflow.md`.
- Review and test before editing (depth scales with lane).
- Keep each iteration independently usable.
- Prefer the smallest change that closes the verified risk.
- Do not introduce architecture the project owner cannot explain.
- Do not add speculative abstractions for future versions.
- Keep group-scoped data isolation as a hard invariant.
- Do not use Agent behavior to replace deterministic backend logic such as permission checks, status filters, hash checks, or CRUD.
- Any write-like Agent/action behavior must have role authorization, group_id isolation, and user confirmation.
- Do not let future work drift into generic RAG or generic Agent framing. If the work affects product direction, tie it back to the Ontology semantic operating layer.
- MCP is a future Agent-facing adapter candidate, not current runtime and not the Ontology itself. Do not add an MCP server/client, SDK, dependency, resource, or tool. See `docs/mcp-agent-boundary-design.md` and `docs/project-status.toml` for current MCP status.
- Frontend F2 is complete. See `docs/project-status.toml` for current project state. Full backend regression uses `--ignore=tests/e2e`.
- Update project memory after Safety Lane iterations; for Standard Lane, only when a meaningful decision was made.
- **Every meaningful change must be committed to Git** (`feat:`, `fix:`, `chore:`, `docs:`, `test:`, `refactor:`).
- Before committing on Standard/Safety Lane: verify related `pytest` and `ruff check` pass. Fast Lane: `git diff --check` + minimal format check only.
- Never commit `.env*` (except `.example`), `*.db`, `.venv/`, `.claude/`, `__pycache__/`, build artifacts, or storage volumes.

## ECC / MCP Context Budget

This project keeps Claude Code MCP surface minimal to avoid tool-definition bloat in the context window.

- **Default (always on):** built-in tools only — file read/write, shell/terminal, git, search. No MCP servers.
- **On-demand only:** Docker, SSH, PostgreSQL, browser/Playwright, GitHub, web search (exa), library docs (context7), ECC memory, ECC multi-agent workflows.
- **How to enable a server for a session:** edit `.claude/settings.local.json` → add the server name to `enabledMcpjsonServers`, or temporarily remove the field.
- **How to disable again:** restore `"enabledMcpjsonServers": []`.
- **Do not** enable the full ECC MCP suite at once — each server adds dozens of tool definitions to every turn.
- **Do not** commit server names that contain personal account handles or instance identifiers.

See `.claude/settings.local.json` for the current allowlist.

## Safety Rules

- Never commit API keys, server passwords, cookies, tokens, or real secrets.
- Do not paste secrets into docs, screenshots, tests, or logs.
- Do not write unpracticed technology into resume-style project claims.
- Do not skip tests because a change is "docs only" if the handoff state claims a fresh verification.
- Do not replace a working simple path with a complex enterprise pattern unless there is a concrete risk being controlled.

## Current Default Commands

Local regression:

```powershell
.\.venv\Scripts\python -m pytest -p no:cacheprovider
```

SQLite migration smoke:

```powershell
$dbPath = "F:\semantic-lighthouse\.tmp\handoff-migration.db"
New-Item -ItemType Directory -Force -Path "F:\semantic-lighthouse\.tmp" | Out-Null
if (Test-Path $dbPath) { Remove-Item $dbPath -Force }
$env:DATABASE_URL = "sqlite+pysqlite:///" + $dbPath.Replace("\\","/").Replace("\","/")
.\.venv\Scripts\python -m alembic upgrade head
.\.venv\Scripts\python -m alembic current
```

Cloud status check:

```bash
cd /opt/semantic-lighthouse
docker compose --env-file .env.production -f docker-compose.prod.yml ps
docker logs semantic-lighthouse-api --tail 100
curl -fsS http://127.0.0.1:8000/health
```

## Iteration Memory Contract

At the end of each iteration, update memory according to lane:

**Safety Lane** — full memory update:
- Update `docs/agent-handoff.md` with current status, verification, risks, and next task.
- Update `docs/engineering-memory/pitfall-log.md` for failures or risks.
- Update `docs/engineering-memory/highlight-log.md` for validated engineering wins.
- Add or update a version retrospective when a version boundary is reached.
- If learning questions were asked, update the matching learning review and `docs/engineering-memory/learning-index.md`.

**Standard Lane** — lightweight:
- Commit with a clear message. Update handoff only at phase boundaries.
- Write engineering memory only when a meaningful architectural decision or tradeoff was made.

**Fast Lane** — commit only:
- Commit and move on. Do not update handoff or engineering memory.
