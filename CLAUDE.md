# Claude Code Handoff Guide

This is the first file Claude Code should read when taking over Semantic Lighthouse.

## Project Intent

Semantic Lighthouse is an enterprise permission-aware RAG / Agent prototype for internship and interview demonstration.

The goal is not to build a productized SaaS. The goal is to prove engineering judgment through a maintainable chain:

```text
auth and group isolation -> document ingestion -> retrieval -> citation-grounded RAG answer -> audit trail -> later Agent workflow
```

Every feature must be explainable by the project owner in business terms, technical terms, risk terms, and interview terms.

## Required Read Order

Before changing code, read these files in order:

1. `README.md`
2. `docs/agent-handoff.md`
3. `docs/engineering-memory/README.md`
4. `docs/engineering-memory/learning-index.md`
5. The most recent retrospective, pitfall log, and highlight log entries
6. `docs/cloud-smoke-playbook.md` when deployment or cloud verification is involved

## Working Rules

- Review and test before editing.
- Keep each iteration independently usable.
- Prefer the smallest change that closes the verified risk.
- Do not introduce architecture the project owner cannot explain.
- Do not add speculative abstractions for future versions.
- Keep group-scoped data isolation as a hard invariant.
- Update project memory after every meaningful iteration.
- **Every meaningful change must be committed to Git** (`feat:`, `fix:`, `chore:`, `docs:`, `test:`, `refactor:`).
- Before committing: verify `pytest` and `ruff check src tests` pass.
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

At the end of each iteration:

- Update `docs/agent-handoff.md` with current status, verification, risks, and next task.
- Update `docs/engineering-memory/pitfall-log.md` for failures or risks.
- Update `docs/engineering-memory/highlight-log.md` for validated engineering wins.
- Add or update a version retrospective when a version boundary is reached.
- If learning questions were asked, update the matching learning review and `docs/engineering-memory/learning-index.md`.
