<!-- Updated: 2026-07-08 | Current snapshot, not generated -->

# Architecture

## System Diagram

```text
Browser /console
    -> FastAPI StaticFiles
    -> static/console.html SPA
    -> FastAPI routers
    -> backend services
    -> SQLAlchemy ORM
    -> PostgreSQL/pgvector or SQLite smoke DB

External providers are optional for local smoke. Fake embedding/chat providers are used by deterministic demos and tests.
```

## Layers

| Layer | Path | Current Shape | Purpose |
|-------|------|---------------|---------|
| Entry | `src/semantic_lighthouse/main.py` | App factory, lifespan, health/docs/console/static mounts | Runtime composition and router registration |
| Routers | `src/semantic_lighthouse/routers/` | 15 files, 16 mounted router objects | HTTP boundary, request validation, dependency injection, group-scoped access |
| Services | `src/semantic_lighthouse/services/` | 26 files | Business logic for ingestion, retrieval, Agent orchestration, ontology modeling, packages, runtime, datasets, outcomes, and audit |
| Models | `src/semantic_lighthouse/models.py` | 29 SQLAlchemy tables | Users, groups, documents, chunks, RAG, conversations, Agent, ontology, tasks, datasets, bindings, runtime audit, projects, outcomes, evidence links |
| Schemas | `src/semantic_lighthouse/schemas.py`, `schemas_dataset.py` | Pydantic contracts | API request/response and dataset-specific contracts |
| Auth | `dependencies.py`, `security.py` | JWT, refresh tokens, role/group dependencies | Server-side identity and authorization context |
| Config | `config.py` | Settings and provider selection | Local/dev/provider/runtime safety configuration |
| Database | `database.py`, `alembic/` | Engine/session plus migrations | Persistence and schema evolution |

## Runtime Boundary

```text
Auth + group isolation
-> document ingestion
-> retrieval evidence
-> citation-grounded RAG
-> user-confirmed task/action
-> controlled Agent workflow
-> ontology governance/modeling/package
-> dataset binding
-> runtime query/traversal
-> outcome artifact
-> governance feedback
```

## Mounted API Areas

| Area | Router Source | Notes |
|------|---------------|-------|
| Auth/groups | `auth.py`, `groups.py` | Login, refresh/logout, membership, invites, join requests |
| Knowledge/RAG | `documents.py`, `rag.py`, `conversations.py` | Upload, ingestion, search, answer runs, chat history |
| Agent/tasks | `agent.py`, `tasks.py` | Controlled orchestration and HITL task confirmation |
| Projects/datasets | `projects.py`, `datasets.py` | Pilot workspace, dataset assets, profiling, bindings |
| Ontology | `ontology.py` | Entities, relations, curation, drafts, packages, evidence draft APIs |
| Runtime/outcomes | `runtime.py`, `evidence_links.py`, `outcomes.py` | Query/traversal, evidence links, pilot outcome records |

## Important Invariants

- `group_id` must come from authenticated server-side context, not client trust.
- Backend services own permission checks, status transitions, hash checks, CRUD, and audit writes.
- Agent behavior coordinates controlled backend operations; it is not an autonomous write plane.
- Runtime MCP is not implemented; `codebase-memory-mcp` is development tooling only.
- Traversal is bounded and typed. Aggregation, SQL-like DSLs, Graph RAG, and autonomous writes remain outside the current runtime boundary.

## Frontend

`static/` is a vanilla JavaScript SPA served by FastAPI. See [frontend.md](frontend.md).
