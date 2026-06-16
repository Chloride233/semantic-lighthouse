# Project Workflows

This document defines repeatable workflows for Semantic Lighthouse. It is meant for Codex, Claude Code, and the project owner, so future sessions can continue without relying on chat history.

## Iteration Workflow

1. Read context:
   - `CLAUDE.md`
   - `README.md`
   - `docs/agent-handoff.md`
   - relevant files under `docs/CODEMAPS/`
   - recent files in `docs/engineering-memory/`

2. Review before editing:
   - `git status --short`
   - inspect changed files if the tree is dirty
   - identify the smallest safe scope

3. Define success criteria:
   - what user-visible behavior changes
   - which tests prove it
   - what must not change

4. Implement narrowly:
   - touch only files required by the task
   - keep architectural changes explainable
   - avoid new frameworks unless the current architecture has a clear bottleneck

5. Verify:
   - choose the appropriate level from `docs/quality-gate.md`
   - record failures and fixes if they teach a reusable lesson

6. Update memory when useful:
   - `docs/agent-handoff.md` for current state and next steps
   - `docs/engineering-memory/pitfall-log.md` for risks and mistakes
   - `docs/engineering-memory/highlight-log.md` for strong engineering decisions
   - version retrospectives only when a meaningful stage completes

7. Commit intentionally:
   - review diff
   - stage only related files
   - use a clear conventional commit message

## Review Workflow

Use when asked to review current changes or another agent's work.

1. Start with `git status --short`.
2. Read the changed files and relevant tests.
3. Prioritize findings:
   - correctness and security
   - permission and `group_id` isolation
   - data lifecycle and auditability
   - test gaps
   - maintainability
4. Run targeted tests only after understanding the diff.
5. Report findings first, then summarize what is good.

## RAG Quality Workflow

Use when answer quality, citations, confidence, or retrieval behavior changes.

1. Check retrieval:
   - keyword
   - semantic
   - hybrid
   - group isolation
   - zero-score or low-quality citation behavior

2. Check answer contract:
   - `answer`
   - `citations`
   - `confidence`
   - `confidence_reason`
   - `evidence_quality`
   - `knowledge_gaps`
   - `next_steps`

3. Check audit:
   - `rag_runs` record exists
   - citations are persisted
   - failures preserve enough error context without leaking secrets

4. Run at least:

```powershell
.\.venv\Scripts\python -m pytest tests\test_rag.py tests\test_retrieval.py tests\test_embeddings.py -q --tb=short --basetemp .tmp\pytest-rag-quality
```

## Frontend Workflow

Use when changing `static/console` or user-facing response fields.

1. Keep the page usable before making it beautiful.
2. Use Chinese UI copy for user-facing workflows.
3. Do not expose raw provider stack traces to users.
4. Verify core browser flows:

```powershell
.\.venv\Scripts\python scripts\verify_ui.py
.\.venv\Scripts\python -m pytest tests\e2e\test_console_e2e.py -q --tb=short --basetemp .tmp\pytest-e2e
```

## Deployment Workflow

Use before or after cloud deployment changes.

1. Verify local:
   - full pytest when deployment changes touch runtime behavior
   - migration smoke when models or migrations changed

2. Deploy with documented commands:
   - see `docs/cloud-smoke-playbook.md`
   - see `docs/deployment-v3-cloud.md`

3. Smoke:
   - `/health`
   - auth login
   - document import/upload
   - retrieval
   - RAG answer

4. Never write real keys, cookies, passwords, or tokens to docs, logs, commits, or test fixtures.

## Deferred Workflow Automation

The public agent architecture research identified several advanced patterns. Current decisions:

- Auto Memory: defer; learning records remain human-reviewed.
- Auto Commit: defer; commits remain explicit review boundaries.
- Docker sandbox: defer until the Agent runs high-risk tools.
- Event-sourced agent log rewrite: defer; current audit tables are sufficient.
- LangGraph/AutoGen integration: defer until workflows become branching or multi-agent enough to justify framework cost.

