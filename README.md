# Semantic Lighthouse / 语义灯塔

企业级权限感知 RAG / Agent 原型。

V1.0 先交付可用的认证与群组权限系统，为后续文档检索、RAG 问答和 Agent 对话建立安全边界。

## V1 Scope

- FastAPI backend
- PostgreSQL via Docker Compose
- SQLAlchemy + Alembic migrations
- BCrypt password hashing
- 15-minute JWT Access Token
- httpOnly Cookie Refresh Token
- Refresh Token Rotation and replay detection
- Owner/Admin/Member group roles
- group_id-scoped authorization checks

## V2 Scope

- Markdown-only document ingestion
- Local import from `F:\ontology-kb\knowledge-graph`
- Single Markdown file upload
- PostgreSQL-backed keyword search
- group_id-scoped `documents` and `document_chunks`
- citation-ready search results with source path and frontmatter metadata

## V2.2 Scope

- MD/TXT/PDF/DOCX document ingestion
- three-stage chunked upload: init, chunks, complete
- instant upload by group-scoped SHA-256 file hash
- resumable upload sessions with uploaded chunk indexes
- idempotent chunk upload by `upload_id + chunk_index`
- local disk-backed upload temp and document storage volumes
- original file metadata on documents

## V2.1 Scope

- Cloud embedding provider abstraction
- Aliyun Model Studio/DashScope embedding configuration
- PostgreSQL pgvector-ready document chunk embeddings
- Manual Owner/Admin embedding rebuild endpoint
- group_id-scoped semantic search endpoint
- Fake embedding provider for local tests

## V3 Scope

- DeepSeek/OpenAI-compatible chat provider abstraction
- `POST /groups/{group_id}/rag/answer`
- `GET /groups/{group_id}/rag/runs`
- `GET /groups/{group_id}/rag/runs/{run_id}`
- keyword or semantic retrieval before generation
- citation-backed answer output
- confidence, knowledge gaps, and next steps
- Fake chat provider for local tests
- local evidence gate: no retrieved citations means no LLM call and a low-confidence answer
- persisted RAG run audit records for replay and evaluation

## V3.4 Scope

- **Async ETL ingestion pipeline** for chunked uploads:
  - `POST /uploads/{id}/complete` creates a document with `status=uploaded` and triggers async ETL.
  - 7-step pipeline: Extract → Parse → Clean → Chunk → Embedding → Load → Finalize.
  - Structure-aware chunking with configurable character limits (target/max/min/overlap).
  - 3-attempt retry with exponential backoff (2s/4s/8s).
  - Ingestion job tracking: `POST/GET /ingestion-jobs` endpoints with group-scoped permissions.
  - Startup crash recovery: orphaned `running` jobs → `failed`, orphaned `processing` docs → `uploaded`.
- **PostgreSQL pgvector HNSW index**: `m=16, ef_construction=200` for <1M vector prototype-scale search.
- **Ready-only retrieval**: keyword search, semantic search, and RAG only return documents with `status=ready`.
- **ETL scope boundary**: chunked upload complete only. `POST /upload` (single file) and `POST /import-local` remain synchronous through `ingest_markdown` — they do not create ingestion jobs.

## Local Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
pip install -e .
docker compose up -d postgres
alembic upgrade head
uvicorn semantic_lighthouse.main:app --reload
```

Open API docs at `http://127.0.0.1:8000/docs`.

For a SQLite smoke run without Docker:

```powershell
$env:DATABASE_URL="sqlite+pysqlite:///./local_v1.db"
alembic upgrade head
powershell -ExecutionPolicy Bypass -File .\scripts\dev\start-v1-api.ps1
```

Stop the smoke-run API:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\dev\stop-v1-api.ps1
```

## Tests

```powershell
pytest
```

Migration check:

```powershell
alembic upgrade head
```

## Demo And Deployment

- Cloud deployment guide: `docs/deployment-v3-cloud.md`
- Cloud smoke playbook: `docs/cloud-smoke-playbook.md`
- Interview demo questions: `docs/interview-demo-questions.md`

## Project Boundary

- Knowledge source for future RAG: `F:\ontology-kb`
- V3 does not implement MinIO, chunked upload, Elasticsearch, hybrid search, rerank, answer persistence, or Agent dialogue.
- Engineering lessons are tracked in `docs/engineering-memory/`.
