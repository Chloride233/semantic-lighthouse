# Semantic Lighthouse Product Brief

## One-Line Positioning

语义灯塔 is a permission-aware knowledge evidence workspace for enterprise AI transformation. Its core is a trusted RAG loop: group-scoped knowledge retrieval, citation-grounded answers, confidence judgment, knowledge gaps, and user-confirmed next-step tasks.

The product boundary source of truth is `docs/product-alignment-prd.md`.

## Why This Project Exists

The project is built for a 2027 AI application / RAG / Agent internship portfolio. Its purpose is to demonstrate that the owner can explain not only model calls, but also the engineering boundary around enterprise AI systems:

- user and group isolation
- document lifecycle
- retrieval quality
- citation traceability
- answer confidence
- auditability
- user-confirmed action handoff
- controlled Agent workflows when multi-step coordination is genuinely needed

## Target User Experience

A user should be able to:

1. register or log in
2. enter a workspace
3. upload or import knowledge documents
4. ask an enterprise AI transformation question
5. inspect the answer, citations, confidence reason, knowledge gaps, and next steps
6. confirm selected next steps into lightweight tasks
7. continue into multi-turn consultation or controlled Agent workflow when needed

The experience should feel like a professional knowledge evidence workspace, not a Swagger-only backend demo and not an unrestricted chatbot.

## Current Product Capabilities

- V1: authentication, refresh-token rotation, role permissions, group isolation
- V2: document ingestion, search, chunk metadata, citation-ready fields
- V2.1: embedding provider abstraction, pgvector-ready semantic search
- V2.2: chunked upload, resumable sessions, MD/TXT/PDF/DOCX parsing
- V3: citation-grounded RAG answer with confidence and knowledge gaps
- V3.3: RAG run audit and history replay
- V3.4: asynchronous ETL pipeline and ingestion jobs
- V4: conversations and controlled tool calling
- Phase 6: Chinese frontend console and knowledge问答 experience
- Phase 7: lightweight Agent orchestration with audit trail
- Product alignment: actionable RAG loop from evidence-backed answer to user-confirmed task

## Product Non-Goals For Now

- full SaaS billing or tenant administration
- complex marketing website
- Kubernetes
- RabbitMQ/Kafka/Celery unless single-machine async ETL becomes a proven bottleneck
- unrestricted autonomous Agent actions
- automatic task creation from every answer
- full project management system
- autonomous web browsing or automatic web-to-KB ingestion
- untested technologies in resume claims

## Quality Bar

A feature is not considered finished until:

- it is runnable locally
- permissions are enforced at API and query level
- tests cover the main success and failure paths
- the risk it controls can be explained
- project memory documents the decision when the feature changes architecture or project narrative

## Current Product Risk Themes

- citation quantity must not be confused with citation quality
- retrieval needs eval metrics, not subjective judgment
- PDF/DOCX parsing is limited to extractable text and ordinary paragraphs
- production deployment must protect secrets and runtime storage
- Agent workflow should remain controlled and auditable before adding framework complexity
- deterministic backend rules should not be replaced by LLM decisions
