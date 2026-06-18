# Development Workflow — Tiered Iteration

Semantic Lighthouse uses a **three-lane risk-tiered workflow**. Not every task needs a full plan, full test suite, full documentation refresh, engineering memory update, and pre-commit review. Choose the lane that matches the risk of the change.

---

## Lane Selection

At the start of every iteration, declare the lane:

```
Lane: Fast / Standard / Safety
Reason: <one sentence explaining why this lane matches the risk>
```

The lane determines verification depth, documentation burden, and planning overhead for that iteration.

---

## Fast Lane

### Applies To

- Documentation changes (`docs/`, `README.md`, comments)
- Prompt / system-prompt tuning
- Minor UI copy or CSS adjustments
- Non-core test fixes (typo, fixture name, assertion message)
- Comment or README small fixes

### Verification

- `git diff --check`
- `git status --short`
- If the change touches a specific file format (e.g. Python, CSS), run the **minimum necessary** format/lint check for that file only

### NOT Required

- Do NOT run full `pytest`
- Do NOT run `ruff check` on the full project
- Do NOT update `docs/agent-handoff.md`
- Do NOT update engineering memory (`pitfall-log.md`, `highlight-log.md`, learning reviews)
- Do NOT write a long plan

### Commit

- Commit with a conventional commit message (`docs:`, `fix:`, etc.)
- Keep the diff small and reviewable

---

## Standard Lane

### Applies To

- Normal backend feature work
- Normal frontend feature work
- Non-permission core logic
- Non-breaking API adjustments
- Routine test additions

### Verification

- Run **related** `pytest` (the test files relevant to the change)
- `ruff check` on changed files
- `git diff --check`
- Run **full** `pytest` at phase completion / handoff boundary, not on every micro-edit

### Required

- Short plan (a few bullet points in the conversation, not a full document)
- Commit with a conventional commit message

### NOT Required

- Do NOT update every entry-point document on every change
- Do NOT write engineering memory entries for routine work

---

## Safety Lane

### Applies To

- Authentication and authorization
- Permission checks and role enforcement
- `group_id` isolation
- Agent write operations or tool execution
- RAG citation grounding and confidence judgment
- Document lifecycle (upload, archive, delete)
- Production configuration (`config.py`, `.env.production`, `docker-compose.prod.yml`)
- Database migrations (Alembic)
- Security audit paths
- Anything that could affect deployment

### Verification

- Run **related** `pytest` first
- Run **full** `pytest`
- `ruff check src tests`
- `git diff --check`
- Smoke check if deployment-relevant (migration, docker compose, health endpoint)

### Required

- Explicit risk description (what could break, who is affected)
- Update `docs/agent-handoff.md` with verification results and risks
- Update engineering memory (`pitfall-log.md` or `highlight-log.md` as appropriate)
- Commit with a conventional commit message

---

## Over-Execution Prohibitions

These rules apply regardless of lane:

1. **Do NOT write a long plan for Fast Lane work.** A one-line reason is enough.
2. **Do NOT run full `pytest` on Fast Lane.** It wastes time and masks the real verification boundary.
3. **Do NOT update all entry-point docs for small changes.** `docs/agent-handoff.md`, engineering memory, and learning reviews are Safety Lane artifacts.
4. **Do NOT use `python -c`, heredoc, or Bash to generate large blocks of code** to work around tool restrictions. If `Edit`/`Write` is blocked by GateGuard, fix the workflow or disable the hook — do not reach for fragile shell-based file writing.
5. **Do NOT cargo-cult the full Safety Lane checklist into Fast or Standard work.** Each lane exists to prevent over-process.

---

## GateGuard Recommendation

This project recommends **against** enabling `pre:edit-write:gateguard-fact-force`.

Reasoning:

- It significantly slows iteration speed by requiring fact-check confirmation on every `Edit`/`Write` operation.
- It induces agents to use unstable shell-based file writing (`python -c`, heredoc, `echo` concatenation) to bypass the hook, which produces broken files more often than it prevents mistakes.
- The security boundary for this project is better enforced by: `AGENTS.md` working rules, `pytest` regression, `git diff` review, secret-prohibition rules, and commit granularity.

Leave GateGuard off by default. Enable it temporarily only when performing a specific audit that benefits from step-by-step confirmation, and disable it again afterward.

---

## Quick Reference

| Concern | Fast | Standard | Safety |
|---------|------|----------|--------|
| Plan required | None | Short (bullet points) | Risk description |
| Related pytest | No | Yes | Yes |
| Full pytest | No | At phase boundary | Yes |
| ruff | Minimal (changed files only) | Changed files | Full `src tests` |
| handoff update | No | No | Yes |
| Engineering memory | No | No | Yes |
| Commit required | Yes | Yes | Yes |
| git diff --check | Yes | Yes | Yes |
