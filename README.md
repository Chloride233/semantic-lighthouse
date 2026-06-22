# Semantic Lighthouse / 语义灯塔

企业 AI 转型 Ontology 语义操作层工作台：帮助企业把碎片化知识、文档、系统和流程，逐步建成权限感知、可审计、可操作、可被 Agent 安全调用的 Ontology 语义层。

当前可信 RAG 闭环是底座：用权限隔离的知识库、引用来源、可信度判断、知识缺口和用户确认任务，把企业 AI 转型知识转化为可审阅的回答和可追踪行动。项目终局不是普通 RAG/Agent，而是面向业务对象、关系、动作、权限、证据和 Agent 接口的语义操作层。

当前产品边界见 `docs/product-alignment-prd.md`。核心链路是：

```text
注册登录 -> 进入群组 -> 上传/导入知识 -> 提问 -> 查看引用/可信度/知识缺口 -> 确认下一步任务 -> Agent/HITL 审计 -> Ontology 治理与图谱 -> 语义操作层
```

Agent 不是默认目标，而是受控协调层：只有多步骤、多工具、需要审计或用户确认的流程才使用 Agent。Phase 8–14 已全部交付。当前项目状态见 `docs/project-status.toml`。

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

## Current Demo Path / 当前可演示链路

**The strongest current demo is the FDE (Future Data Engineer) Delivery Chain**:

```powershell
# Full FDE chain with manufacturing data pack
.\.venv\Scripts\python scripts\smoke_fde_demo.py \
    --data-pack .tmp\phase19-manufacturing

# Generate the data pack first
.\.venv\Scripts\python scripts\generate_manufacturing_dataset.py \
    --preset tiny --output-dir .tmp\phase19-manufacturing
```

Result: **11/11 PASS, artifact gate PASS (0 findings), ~0.7s**.

### Phase 19 Ontology Pipeline (data → governance)

```powershell
# 1. Generate
.\.venv\Scripts\python scripts\generate_manufacturing_dataset.py \
    --preset tiny --output-dir .tmp\phase19-manufacturing

# 2. Validate data pack
.\.venv\Scripts\python scripts\validate_manufacturing_data_pack.py \
    .tmp\phase19-manufacturing

# 3. Generate mapping contract
.\.venv\Scripts\python scripts\generate_mapping_contract.py \
    --data-pack .tmp\phase19-manufacturing

# 4. Validate mapping contract
.\.venv\Scripts\python scripts\validate_mapping_contract.py \
    --data-pack .tmp\phase19-manufacturing

# 5. Run business rules
.\.venv\Scripts\python scripts\validate_business_rules.py \
    --data-pack .tmp\phase19-manufacturing

# 6. Generate governance feedback
.\.venv\Scripts\python scripts\generate_governance_feedback.py \
    --data-pack .tmp\phase19-manufacturing
```

Full pipeline: CSV → manifest → mapping_contract → rule_validation → governance_feedback.

Complete chain with FDE:

```text
manufacturing CSV → manifest → mapping_contract → rule validation → governance feedback
registration → login → group → project → evidence → package
→ runtime → outcome → markdown artifact → quality gate
```

- Smoke script: zero external dependencies (fake embedding + fake chat), temporary SQLite, no API keys needed
- FDE deliverables: outcome record + outcome-summary JSON + bounded markdown artifact
- Markdown artifact: 7 required sections, 11 forbidden terms, 5 boundedness rules quality gate
- Interview script: `docs/interview-demo-questions.md` (5-min demo + 5 FAQ)
- Portfolio narrative: `docs/portfolio-demo-narrative.md`

## Demo And Deployment

- Portfolio narrative: `docs/portfolio-demo-narrative.md`
- Cloud deployment guide: `docs/deployment-v3-cloud.md`
- Cloud smoke playbook: `docs/cloud-smoke-playbook.md`
- Interview demo questions: `docs/interview-demo-questions.md`

## Project Boundary

- Knowledge source and Ontology seed corpus: `F:\ontology-kb`
- Phases 8–19 delivered: RAG → tasks → Agent/HITL → ontology governance → modeling drafts → quality-gated packages → business contracts → pilot projects → evidence feedback loop → FDE outcome records → cloud deployment → manufacturing ontology pipeline. See `docs/project-status.toml` for current phase.
- Intentionally deferred: full modeling studio, Graph RAG, MCP runtime, Agent auto-write, Neo4j, OWL, LangGraph, Kubernetes. See `docs/portfolio-demo-narrative.md` and `docs/product-alignment-prd.md` for rationale.
- Engineering lessons tracked in `docs/engineering-memory/`.
