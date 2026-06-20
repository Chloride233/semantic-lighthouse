# Semantic Lighthouse Product Brief

## One-Line Positioning

语义灯塔 is an ontology-oriented semantic operating layer workspace for enterprise AI transformation. It helps enterprises turn fragmented knowledge, documents, systems, and workflows into a permission-aware, auditable, actionable Ontology semantic layer that can be safely used by applications and Agent workflows.

The current trusted RAG loop is the foundation: group-scoped knowledge retrieval, citation-grounded answers, confidence judgment, knowledge gaps, user-confirmed next-step tasks, and controlled Agent/HITL audit. The product destination is broader than RAG: an enterprise Ontology made of business objects, properties, relationships, actions, permissions, evidence, and Agent-facing interfaces.

The product boundary source of truth is `docs/product-alignment-prd.md`.

## Why This Project Exists

The project is built for a 2027 AI application / RAG / Agent internship portfolio. Its purpose is to demonstrate that the owner can explain not only model calls, but also the engineering boundary around enterprise AI systems and the product path from trusted evidence to an Ontology semantic operating layer:

- user and group isolation
- document lifecycle
- retrieval quality
- citation traceability
- answer confidence
- auditability
- user-confirmed action handoff
- controlled Agent workflows when multi-step coordination is genuinely needed
- ontology governance, entity/relation visibility, and semantic-layer evolution

## Target User Experience

A user should be able to:

1. register or log in
2. enter a workspace
3. upload or import knowledge documents
4. ask an enterprise AI transformation question
5. inspect the answer, citations, confidence reason, knowledge gaps, and next steps
6. confirm selected next steps into lightweight tasks
7. continue into multi-turn consultation or controlled Agent workflow when needed
8. inspect ontology governance issues, entity/relation structure, and modeling gaps as the product evolves

The experience should feel like a professional semantic operating layer workspace, not a Swagger-only backend demo, not a generic RAG chatbot, and not an unrestricted autonomous Agent.

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
- Phase 8: experience integration for the demonstrable loop: RAG -> user-confirmed task -> Agent/HITL -> audit
- Phase 9 delivered: Ontology Core v1 — schema/frontmatter validation, entity extraction, wikilink relation extraction, governance issue list, ontology graph, and entity detail UI. Real KB demo: 74 docs → 74 entities, 186 relations, 97 issues.
- Phase 10 delivered: Governance Operations — issue triage, real KB curation demo (97 issues → 39 backlog entries), graph UX polish, evidence-to-ontology bridge, end-to-end review.
- Phase 11/12 delivered: Ontology Modeling Drafts v1 + Model Quality & Contract Packages v1 — see `docs/phase11-planning.md` and `docs/phase12-planning.md`.
- Phase 13: Typed Business Ontology Contract & Manufacturing Pilot v1 — delivered.
- Phase 14: Business Pilot Project main chain (goal→data→model→validate→pilot) — delivered (backend complete, Frontend F2A active).
- Frontend F2: Guided Business Pilot workspace — F2A delivered.

## Product Non-Goals For Now

- full SaaS billing or tenant administration
- complex marketing website
- Kubernetes
- RabbitMQ/Kafka/Celery unless single-machine async ETL becomes a proven bottleneck
- unrestricted autonomous Agent actions
- automatic task creation from every answer
- full project management system
- autonomous web browsing or automatic web-to-KB ingestion
- full manual Ontology modeling studio before governance and graph visibility
- Graph RAG before the entity/relation read model is reliable
- Agent auto-writing Ontology objects, relations, or actions
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
- Agent workflow should remain controlled and auditable before adding framework complexity. The next product gap is not backend Agent capability, but making existing controlled Agent workflows visible and usable in the frontend.
- deterministic backend rules should not be replaced by LLM decisions
- Ontology direction must not be reduced to "more RAG". Phase 9 made the knowledge base governable as entities, relations, validation issues, graph, and entity detail. Phase 10 delivered governance operations: issue triage, curation demo, graph UX polish, evidence bridge. Phase 11/12 delivered modeling drafts, quality gates, and immutable model packages. Phase 13 planning focuses on typed business ontology contracts before Graph RAG, full modeling studio, or Agent auto-write.
