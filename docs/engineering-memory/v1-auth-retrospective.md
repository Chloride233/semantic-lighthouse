# V1 Auth Retrospective

## Current Status

V1 implementation has been scaffolded with FastAPI, SQLAlchemy models, Alembic migration, authentication routes, group routes, API tests, and Docker Compose for PostgreSQL.

## What V1 Is Supposed To Prove

- Passwords are stored as BCrypt hashes.
- Access Tokens are short-lived and stateless.
- Refresh Tokens are stateful, stored as hashes, and rotated.
- Refresh replay is detected and revokes the token family.
- Groups have Owner/Admin/Member roles.
- Group APIs enforce authentication, role checks, and group_id filtering.

## Open Verification Items

- Start PostgreSQL via Docker Compose once Docker is installed on the workstation.
- Run Alembic migration against PostgreSQL.
- Start FastAPI and manually verify `/docs` plus the main auth/group flows.

## Verified So Far

- Python dependencies installed in `.venv`.
- Application imports successfully after editable package install.
- Alembic migration runs against a temporary SQLite database.
- API regression tests pass: 14 passed.
- SQLite smoke API service starts on `http://127.0.0.1:8000`.
- Smoke flow passed: register, login, `/auth/me`, create group as owner.
- Refresh replay smoke passed: replaying an old refresh token returns 401 and revokes the newer token in the same family.
- Group permission smoke passed: member cannot list/approve join requests, outsider cannot access group, owner can approve.
- Docker Desktop is installed and Docker Engine is running.
- PostgreSQL container starts through Docker Compose.
- Alembic migration runs against PostgreSQL.
- PostgreSQL-backed HTTP smoke passed: register/login/me/create group.
- PostgreSQL-backed refresh replay smoke passed.
- PostgreSQL-backed group authorization failure-path smoke passed.
- V1.1 `/console` resource and auth-flow smoke passed on PostgreSQL-backed runtime.

## Environment Gap

Resolved. Docker Desktop initially failed because WSL2/Windows Hypervisor was not fully active (`hypervisorlaunchtype Off`). After enabling Hypervisor launch and confirming WSL2 Ubuntu could run, Docker Engine started successfully.

## PostgreSQL Verification Checklist

Run these after Docker Desktop is installed and running:

```powershell
docker --version
docker compose up -d postgres
$env:DATABASE_URL="postgresql+psycopg://semantic_lighthouse:semantic_lighthouse@localhost:5432/semantic_lighthouse"
.\.venv\Scripts\alembic upgrade head
powershell -ExecutionPolicy Bypass -File .\scripts\dev\start-v1-api.ps1 -DatabaseUrl $env:DATABASE_URL
```

Then repeat the smoke flows:

- `/health`
- register/login/me/create group
- refresh token replay
- member/outsider authorization failures

Status: completed on PostgreSQL-backed runtime.
