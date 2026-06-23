# Claude Code Entry

This file is the Claude-specific entry point for Semantic Lighthouse. Shared project rules live in `AGENTS.md`.

@import AGENTS.md

When Claude Code leaves `@import` as literal text, read `AGENTS.md`, then read its imported files.

## Claude-Specific Context Budget

- Start with built-in file, shell, git, and search tools.
- Use the current project's configured `codebase-memory-mcp` per `AGENTS.md` for code structure, architecture, symbols, routes, call chains, impact analysis, and snippets.
- Treat the project name returned by `list_projects` as authoritative.
- Use `rg` for ordinary text search, exact-string search, non-code files, and fallback when the MCP tool is unavailable.
- Product runtime MCP remains governed by `AGENTS.md` and `docs/project-status.toml`.

## Default Handoff

Use this final-response shape after code or documentation edits:

```text
Scope completed:
- ...

Verification run:
- <command> -> <result>

Commit:
- <hash/message>
```

For Safety Lane, include the risk and handoff/memory updates required by `docs/development-workflow.md`.
