# Claude Code Entry

This file is the Claude-specific entry point for Semantic Lighthouse. Shared project rules live in `AGENTS.md`.

@import AGENTS.md

When Claude Code leaves `@import` as literal text, read `AGENTS.md`, then read its imported files.

## Claude-Specific Context Budget

- Start with built-in file, shell, git, and search tools.
- Enable extra MCP servers only for the task that needs them, then return to the minimal surface.
- `codebase-memory-mcp` is the approved developer code-graph exception for architecture, symbols, routes, call chains, impact analysis, and snippets. Project name: `F-semantic-lighthouse`.
- Product MCP runtime remains governed by `AGENTS.md` and `docs/project-status.toml`.

## Claude Local MCP Notes

- Session allowlist lives in `.claude/settings.local.json`.
- Add a server name to `enabledMcpjsonServers` only for the current task.
- Restore `"enabledMcpjsonServers": []` after the task when the extra server leaves the active scope.
- Keep personal account handles, instance IDs, tokens, cookies, and keys out of committed settings and docs.

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
