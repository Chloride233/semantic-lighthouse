# Quality Gate

This project uses quality gates to keep each iteration explainable, testable, and reversible. The goal is not to run every command after every tiny edit, but to choose a gate that matches the risk of the change.

## Principles

- Review before coding when the problem is unclear.
- Make small, scoped changes.
- Run targeted tests first, then broader tests when the touched surface is shared.
- Do not commit secrets, `.env` files, uploaded documents, generated databases, logs, or temporary runtime files.
- Do not use fake providers to hide failures in real-provider workflows.
- Commit only after the diff has been reviewed and the relevant checks have passed.

## Gate Levels

### Level 0: Documentation Only

Use when only Markdown docs or prompts changed.

```powershell
git diff --check
git status --short
```

Expected result: no whitespace errors; only intended files changed.

### Level 1: Narrow Backend Change

Use when changing one service/router/schema with a clear test area.

```powershell
git diff --check
.\.venv\Scripts\python -m pytest <targeted-test-file> -q --tb=short --basetemp .tmp\pytest-targeted
```

Examples:

```powershell
.\.venv\Scripts\python -m pytest tests\test_rag.py -q --tb=short --basetemp .tmp\pytest-rag
.\.venv\Scripts\python -m pytest tests\test_retrieval.py -q --tb=short --basetemp .tmp\pytest-retrieval
```

### Level 2: Shared Backend Contract

Use when changing retrieval, RAG, auth, document lifecycle, embeddings, conversations, or schemas used by multiple routes.

```powershell
git diff --check
.\.venv\Scripts\python -m pytest tests\test_rag.py tests\test_retrieval.py tests\test_embeddings.py -q --tb=short --basetemp .tmp\pytest-shared
```

Add more suites based on scope:

```powershell
.\.venv\Scripts\python -m pytest tests\test_conversations.py tests\test_chat_client.py -q --tb=short --basetemp .tmp\pytest-chat
```

### Level 3: Frontend Or User Flow Change

Use when changing `static/console` or frontend-facing response shapes.

```powershell
git diff --check
.\.venv\Scripts\python scripts\verify_ui.py
.\.venv\Scripts\python -m pytest tests\e2e\test_console_e2e.py -q --tb=short --basetemp .tmp\pytest-e2e
```

### Level 4: Migration Or Deployment-Sensitive Change

Use when changing Alembic migrations, database models, Docker, deployment scripts, or startup behavior.

```powershell
git diff --check
.\.venv\Scripts\python -m pytest -q --tb=short --basetemp .tmp\pytest-full
```

Run an empty-database migration smoke if the change affects migrations or models:

```powershell
$dbPath = "F:\semantic-lighthouse\.tmp\migration-smoke.db"
if (Test-Path $dbPath) { Remove-Item $dbPath -Force }
$env:DATABASE_URL = "sqlite+pysqlite:///" + $dbPath.Replace("\", "/")
.\.venv\Scripts\python -m alembic upgrade head
.\.venv\Scripts\python -m alembic current
```

## Always Check Before Commit

```powershell
git status --short
git diff --check
git diff --cached --stat
git diff --cached --name-only
```

Commit message examples:

```text
fix: prevent hybrid retrieval from returning zero-score citations
feat: explain rag evidence quality
docs: add public agent architecture research report
```

## Current Known Warnings

- `StarletteDeprecationWarning` from FastAPI TestClient is currently tolerated.
- Pytest cache warnings may appear in sandboxed Windows runs. Use `--basetemp .tmp\...` to avoid temp-directory permission problems.

