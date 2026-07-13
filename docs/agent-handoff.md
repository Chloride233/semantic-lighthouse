# Semantic Lighthouse Agent Handoff

Current product state, evidence phase, next decision gate, verification counts,
and known risks live only in [`project-status.toml`](project-status.toml). Do not
copy those values into this document.

## Session Start

1. Read `docs/project-status.toml`.
2. Read `docs/development-workflow.md` and declare the lane.
3. Run `git status --short`.
4. Run `git log --oneline -5`.
5. Load only the code, tests, and supporting documents required by the current
   decision gate.

## Durable Boundaries

- Derive `group_id`, membership, and role from authenticated server context.
- Backend services own permissions, state transitions, CRUD, and audit writes.
- Agent output is untrusted input to registered tools and deterministic backend
  controls.
- Risky writes require explicit user confirmation and persisted audit evidence.
- Keep storage paths, secrets, and unreviewed external data out of responses and
  committed artifacts.
- Runtime MCP remains out of scope until a dedicated Safety Lane phase approves
  identity, authorization, audit, provenance, and HITL boundaries.

## Handoff Discipline

Update `docs/project-status.toml` when verified product state changes. Keep this
entry document stable, record exact verification commands and outcomes, and do
not present plans or deferred scope as delivered behavior.
