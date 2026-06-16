# Semantic Lighthouse Product Brief

## One-Line Positioning

语义灯塔 is an enterprise AI transformation consultant prototype: it uses a permission-isolated knowledge base to answer business questions with citations, confidence judgment, knowledge gaps, and next-step suggestions.

## Why This Project Exists

The project is built for a 2027 AI application / RAG / Agent internship portfolio. Its purpose is to demonstrate that the owner can explain not only model calls, but also the engineering boundary around enterprise AI systems:

- user and group isolation
- document lifecycle
- retrieval quality
- citation traceability
- answer confidence
- auditability
- controlled Agent workflows

## Target User Experience

A user should be able to:

1. register or log in
2. enter a workspace
3. upload or import knowledge documents
4. ask a consulting-style question
5. inspect the answer, citations, confidence reason, knowledge gaps, and next steps
6. continue into multi-turn consultation when needed

The experience should feel like a professional knowledge-consulting workspace, not a Swagger-only backend demo.

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

## Product Non-Goals For Now

- full SaaS billing or tenant administration
- complex marketing website
- Kubernetes
- RabbitMQ/Kafka/Celery unless single-machine async ETL becomes a proven bottleneck
- unrestricted autonomous Agent actions
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
