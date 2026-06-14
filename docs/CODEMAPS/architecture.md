<!-- Generated: 2026-06-12 | Files: 35 | ~600 tokens -->

# Architecture

## System Diagram

```
Browser /console ──→ FastAPI StaticFiles ──→ static/console.html (SPA)
                         │
Browser fetch ──────→ FastAPI Routers ──→ Services ──→ SQLAlchemy ──→ PostgreSQL/pgvector
                         │                      │
                    [Auth middlewares]     [Embedding APIs]
                         │                      │
                    JWT+cookie auth        Aliyun DashScope
                                           DeepSeek Chat
```

## Layers

| Layer | Dir | Files | Purpose |
|-------|-----|-------|---------|
| Entry | `main.py` | 1 | App factory, lifespan, `/health`, `/console`, router registration |
| Routers | `routers/` | 6 | HTTP endpoints, dependency injection, request validation |
| Services | `services/` | 7 | Business logic: chat, ETL, retrieval, embeddings, uploads, files |
| Models | `models.py` | 1 | SQLAlchemy ORM: 12 tables, relationships, type definitions |
| Schemas | `schemas.py` | 1 | Pydantic request/response models, field validators |
| Auth | `dependencies.py` + `security.py` | 2 | JWT encode/decode, Bearer extraction, group membership check |
| Config | `config.py` | 1 | Pydantic Settings: env vars, provider configs, dimension constants |
| Database | `database.py` | 1 | SQLAlchemy engine, SessionLocal, Alembic migrations |

## Key Constants

- `PGVECTOR_DIMENSION = 1024` (`routers/_shared.py`)
- `HISTORY_ROUNDS = 10` (`routers/conversations.py`)
- `AVAILABLE_TOOLS = [search_knowledge_base]` (`routers/conversations.py`)
- `HNSW m=16, ef_construction=200` (`alembic/.../0006_v34_ingestion_jobs.py`)

## Router → Service Dependencies

```
auth         ──→ security.py
documents    ──→ retrieval, embeddings, document_uploads, document_files, document_etl
rag          ──→ retrieval, embeddings, chat
conversations──→ retrieval, embeddings, chat
agent        ──→ agent_orchestrator, retrieval
groups       ──→ (self-contained)
```

## Static Frontend

`static/` — Served by FastAPI `StaticFiles` mount. Vanilla JS ES modules, hash router. Zero npm/build. See [frontend.md](frontend.md).
