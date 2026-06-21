# Phase 18 Planning — Cloud Deployment Smoke v1

Status: 18.1 DELIVERED — 18.2 BLOCKED (Docker daemon unavailable) — 18.3–18.5 pending.

## Decision

Phase 18 proves the FDE demo chain (Phase 14–17) runs **beyond local SQLite**,
in an environment close to the target deployment shape: PostgreSQL + pgvector
via Docker Compose, with uvicorn serving the API.

```text
Docker Compose (PostgreSQL + pgvector + FastAPI)
→ Alembic migration to head (0027)
→ /health endpoint (DB + provider status)
→ Auth smoke (register + login + group + project)
→ FDE outcome chain (outcomes CRUD + summary + artifact)
→ Markdown artifact quality gate
→ Smoke report: PASS/FAIL with per-step timing
```

This phase does NOT add new features. It **validates deployability** of the
existing chain — the strongest portfolio signal for a 2027 engineering review.

## Why This Is Next

### The current gap

Phase 17 proved the FDE chain works locally:
- `scripts/smoke_fde_demo.py` — 11/11 PASS, ~0.8s, temp SQLite
- Fake providers, TestClient in-process, no real I/O

But a reviewer asks: "Does this actually work on a real database?"

Without Phase 18, the answer is "it should" — based on code paths and tests,
but never demonstrated end-to-end on PostgreSQL.

### What Phase 18 proves

- The Alembic migration chain (`0001 → 0027`) works on PostgreSQL (not just SQLite smoke).
- The API starts under uvicorn, not just TestClient.
- `/health` returns DB status on a real pgvector database.
- Auth + FDE outcome endpoints work end-to-end with real HTTP.
- The markdown artifact passes quality gate in deployment context.

### Why this is higher priority than remaining candidates

| Candidate | Why deferred or lower priority |
|-----------|-------------------------------|
| Ontology operationalization with real data | Requires real CMMS/ERP data sourcing and ETL — large scope, not a demo gap |
| 16.3 Front-end outcome panel | Frontend work; backend chain already proven |
| Full test suite audit | Runs on SQLite; doesn't prove deployability |
| New RAG/Agent features | Chain is feature-complete for demo |

**Phase 18 is the missing proof that the project is deployable**, not just a
local prototype. This is the single strongest portfolio signal available.

## Scope

### In scope

- **18.1 Deployment config audit**: Review `.env.example`, `docker-compose.prod.yml`,
  `Dockerfile`, `config.py`, Alembic `env.py` for:
  - `DATABASE_URL` format for PostgreSQL vs SQLite.
  - `JWT_SECRET_KEY` minimum length enforcement (`APP_ENV=production`).
  - `EMBEDDING_PROVIDER` / `CHAT_PROVIDER` — fake for smoke, real optional.
  - Storage volume mappings for document uploads and datasets.
  - pgvector extension availability check on startup.
  - Document any gaps found; apply minor config/doc fixes only.
- **18.2 Migration smoke on PostgreSQL**: Using a temporary PostgreSQL instance
  (local Docker or `.tmp/`-scoped compose), run `alembic upgrade head` and
  verify all 27 migrations apply cleanly. Not a production migration.
- **18.3 HTTP health/API smoke**: After Docker Compose starts the API, call:
  - `GET /health` → 200, DB connected, providers configured.
  - `POST /auth/register` → 201.
  - `POST /auth/login` → 200, valid JWT.
  - `POST /groups` → 201.
  - `POST /groups/{gid}/projects` → 201.
  - `POST /groups/{gid}/projects/{pid}/outcomes` → 201.
  - `GET /groups/{gid}/projects/{pid}/outcome-summary` → 200.
  - `GET /groups/{gid}/projects/{pid}/outcome-artifact.md` → 200, text/markdown.
- **18.4 FDE smoke deployment adapter**: Optionally extend `scripts/smoke_fde_demo.py`
  to support a `--base-url` mode (real HTTP calls instead of TestClient).
  DB seed steps remain TestClient-local; API calls go through HTTP.
  If too complex for v1, defer to Phase 19 and keep 18.3 as the deployment smoke.
- **18.5 Closeout review**: Record deployment smoke results, document risks,
  update handoff, mark Phase 18 complete.

### Out of scope (hard boundaries)

- No cloud resource creation (no Terraform, no AWS/阿里云 API calls).
- No Docker image push to registry.
- No real LLM API keys (use fake providers unless explicitly configured).
- No real enterprise data.
- No frontend changes.
- No MCP runtime.
- No Graph RAG.
- No Kubernetes or multi-service orchestration.
- No HTTPS/TLS/domain setup.
- No production security hardening beyond existing `APP_ENV=production` checks.
- No CI/CD pipeline.

## Suggested Slices

### 18.1 — Deployment Config Audit ← DELIVERED 2026-06-21

**Lane: Fast (docs + minor config fixes only).**

**Audit results**:

| # | Item | Status | Detail |
|---|------|--------|--------|
| 1 | DATABASE_URL for PostgreSQL | ✅ PASS | `.env.example`, config.py default, and `docker-compose.prod.yml` all use correct PostgreSQL format |
| 2 | JWT_SECRET_KEY | ✅ PASS | Placeholder documented; prod safety check requires ≥32 chars and non-default |
| 3 | EMBEDDING_PROVIDER / CHAT_PROVIDER fake mode | ✅ FIXED | Added comments to `.env.example` documenting `fake` provider for deployment smoke |
| 4 | COOKIE_SECURE | ✅ PASS | Dev default `false`; production requires `true` via safety check |
| 5 | Storage / upload paths | ✅ FIXED | Added missing `DATASET_STORAGE_PATH` to `.env.example`; all paths volume-mapped in prod compose |
| 6 | pgvector extension | ✅ PASS | `pgvector/pgvector:pg17` image includes pgvector; no separate CREATE EXTENSION needed |
| 7 | Alembic upgrade head | ✅ PASS | `scripts/docker/start-api.sh` runs migrations before uvicorn; `env.py` reads settings correctly |
| 8 | Health check endpoint | ✅ PASS | `docker-compose.prod.yml` healthcheck uses `curl /health`; Dockerfile installs curl |
| 9 | No secrets committed | ✅ PASS | `.env.example` uses placeholders; `.env.production` is gitignored |
| 10 | APP_ENV variable | ✅ FIXED | Added `APP_ENV=development` to `.env.example` (was missing; config.py default is "development") |
| 11 | Cloud smoke playbook | ✅ FIXED | Added Chain 5 (FDE Outcome Delivery) with curl examples and passing criteria |

**Fixes applied** (3 files):
- `.env.example`: Added `APP_ENV`, `DATASET_STORAGE_PATH`, section headers (App/Storage/Embedding/Chat/Agent), comments for `fake` provider smoke mode
- `docs/cloud-smoke-playbook.md`: Added Chain 5 (FDE) with curl commands, passing criteria, and local smoke reference; updated interview version text
- No code changes; no migration; no frontend

**Next**: 18.2 PostgreSQL migration smoke.

### 18.2 — Migration Smoke on PostgreSQL ← BLOCKED 2026-06-21

**Lane: Standard (requires Docker daemon).**

**Status**: Docker CLI available (v29.5.3) but Docker Desktop daemon not running
(`dockerDesktopLinuxEngine` pipe not found). Cannot start temporary PostgreSQL
container. Blocked until Docker Desktop is started.

**Procedure (to execute when Docker available)**:

```bash
docker run -d --name sl-phase18-migration-smoke \
  -e POSTGRES_PASSWORD=smoke \
  -e POSTGRES_DB=sl_smoke \
  -p 54329:5432 \
  pgvector/pgvector:pg17

until docker exec sl-phase18-migration-smoke pg_isready -U postgres; do sleep 1; done

DATABASE_URL="postgresql+psycopg://postgres:smoke@localhost:54329/sl_smoke" \
  .venv/Scripts/python -m alembic upgrade head

DATABASE_URL="postgresql+psycopg://postgres:smoke@localhost:54329/sl_smoke" \
  .venv/Scripts/python -m alembic current

docker stop sl-phase18-migration-smoke
docker rm sl-phase18-migration-smoke
```

Expected: `0027_v27_pilot_outcome_records (head)`, no errors.

**Next**: Retry when Docker Desktop is available, or proceed to 18.3 (HTTP health/API smoke)
using local uvicorn + SQLite if Docker remains unavailable.

### 18.3 — HTTP Health/API Smoke

**Lane: Standard.**

After Docker Compose starts the full stack:

```bash
# Health
curl -fsS http://127.0.0.1:8000/health
# → {"status":"ok","database":"connected","embedding_provider":"fake","chat_provider":"fake"}

# Auth
TOKEN=$(curl -sS -X POST http://127.0.0.1:8000/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"smoke@deploy.local","password":"SmokePass1","display_name":"Smoke Op"}' \
  | ...)

# FDE chain
curl -sS -X POST http://127.0.0.1:8000/groups -H "Authorization: Bearer $TOKEN" ...
# ...
```

Cover the minimum: health, register, login, create group, create project,
create outcome, fetch summary, fetch artifact.

This can be a section in the smoke script or a standalone shell snippet.
Prefer integrating into `scripts/smoke_fde_demo.py` with a `--base-url` flag
(see 18.4).

### 18.4 — FDE Smoke Deployment Adapter

**Lane: Standard (if implemented) or deferred.**

Goal: make `scripts/smoke_fde_demo.py` work against a running API server
instead of TestClient.

Proposed design:
- Add `--base-url http://127.0.0.1:8000` flag.
- When `--base-url` is set: use `requests` (or `httpx`) for API calls;
  keep DB seed steps as direct SQLAlchemy (they need the same DB session).
  OR: run all steps through the API, seeding evidence/packages/runtime
  via direct DB connection to the PostgreSQL instance.
- When not set: use TestClient as today (backward compatible).

If this is too complex for v1: defer to Phase 19. Phase 18.3 provides
sufficient deployment smoke coverage for closeout.

### 18.5 — Closeout Review

**Lane: Standard (review).**

Verify:
- Config audit complete; any gaps documented.
- Migration smoke passes on PostgreSQL (manual or scripted).
- Health/API smoke passes against running Docker Compose stack.
- Artifact quality gate passes on deployment-generated markdown.
- Docs aligned (`check_doc_alignment.py`).
- No regressions in existing 66 Phase 16 tests.
- `migration_head` still 0027 (no new migrations).

## Hard Boundaries

- No cloud resource creation.
- No image push.
- No real LLM API keys (fake providers default).
- No real enterprise data.
- No frontend changes.
- No MCP / Graph RAG / Agent auto-write.
- No Kubernetes / multi-service.
- No HTTPS/TLS/domain.
- No CI/CD.
- No new database migrations (0027 is current head).

## Product Alignment Check

| PRD principle | How Phase 18 honors it |
|---------------|------------------------|
| "A feature is not finished until it is runnable locally" | Deployment smoke proves runnability beyond local dev |
| "Every capability explainable in business, technical, risk, and interview terms" | "Runs on PostgreSQL + Docker" is the strongest technical signal |
| "Keep group-scoped data isolation as a hard invariant" | Verified on PostgreSQL, not just SQLite |
| "No speculative abstractions" | No new features — just deployability verification |

## Verification (Planning Phase)

- `scripts/check_doc_alignment.py` — confirm all docs reference Phase 18 planning.
- `git diff --check` — no whitespace errors.
- `git status --short` — only planning docs changed.
- No pytest, ruff, verify_ui, or e2e (no code changed).

## Open Decisions (resolved during implementation)

1. 18.4 smoke adapter: implement now vs. defer to Phase 19. **Recommendation**: defer
   to Phase 19 unless trivial. 18.3 health/API smoke is sufficient for Phase 18 closeout.
2. Temporary PostgreSQL: local Docker vs. cloud server. **Recommendation**: local Docker
   for speed; manual cloud procedure as fallback.
3. Whether to create `.env.smoke` with fake provider defaults for deployment smoke.
   **Recommendation**: yes — a dedicated smoke env file prevents accidental real-API calls.
