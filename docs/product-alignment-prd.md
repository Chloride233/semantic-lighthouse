# Semantic Lighthouse Product Alignment PRD

Last updated: 2026-06-18

## 1. Product Positioning

Semantic Lighthouse / 语义灯塔 is an ontology-oriented semantic operating layer workspace for enterprise AI transformation.

It helps enterprises turn fragmented knowledge, documents, systems, and workflows into a permission-aware, auditable, actionable Ontology semantic layer that can be safely used by people, applications, and controlled Agent workflows.

The product is not a general chatbot, not a full SaaS product, not a generic RAG demo, and not an unrestricted autonomous Agent platform. Its current trusted RAG and Agent capabilities are foundations for the larger Ontology direction.

The north star:

```text
fragmented knowledge/documents/systems/workflows
-> trusted evidence and user-confirmed action
-> governed entities and relationships
-> business objects, actions, permissions, and Agent interfaces
-> enterprise Ontology semantic operating layer
```

Every capability must be explainable in business terms, technical terms, risk terms, and interview terms.

## 2. Working Definition: Ontology Semantic Operating Layer

In this project, Ontology means the enterprise semantic operating layer.

It is the layer that models:

- **business objects**: customer, order, equipment, work order, supplier, project
- **properties**: status, owner, risk level, amount, timestamp, confidence, maturity
- **relationships**: customer owns order, equipment links to work order, vendor supports product
- **actions**: approve, archive, create task, trigger review, request confirmation
- **permissions and governance**: who can read, write, confirm, archive, or execute
- **evidence**: citations, source maturity, retrieval records, audit trails
- **Agent-facing interfaces**: safe tools and action surfaces that preserve group isolation and HITL

Ontology is not merely:

- a database schema
- a static knowledge graph
- a set of Markdown frontmatter fields
- a vector index
- a RAG document library
- an Agent framework

The current trusted evidence/action foundation manages the path from knowledge to judgment to action:

```text
group-isolated knowledge -> retrieval evidence -> RAG answer -> confidence/gaps -> next steps -> confirmed task/action
```

Phase 9 extends that foundation toward Ontology by making entities, relationships, schema validity, broken links, and governance issues visible.

## 3. Target Users And Scenarios

### Primary User For This Project

The project owner, using the system as a job-portfolio demonstration of enterprise RAG, Agent, and Ontology engineering judgment.

### Future Product-Like Users

- AI transformation consultant preparing client-facing answers and ontology pilot plans.
- Enterprise knowledge operator maintaining ontology-ready knowledge assets.
- Business engineer mapping documents and workflows into business objects, relationships, and actions.
- Team member checking whether a recommendation is grounded in approved internal knowledge and aligned with the semantic model.

### Core Scenario

The near-term workflow remains:

1. User logs in and enters a group workspace.
2. User uploads or imports enterprise AI transformation knowledge.
3. System retrieves group-scoped evidence.
4. System returns answer, citations, confidence, knowledge gaps, and next steps.
5. User confirms selected next steps into lightweight tasks.
6. Controlled Agent workflows coordinate multi-step/tool-based work with HITL and audit.

The next product workflow adds:

1. System validates schema/frontmatter and wikilinks in the knowledge base.
2. System extracts ontology entities and relationships from approved documents.
3. User inspects entity list, relation graph, broken links, and governance issues.
4. Future modeling workflows turn validated entities into Object Type, Property, Link Type, and Action Type drafts.

## 4. Current Phase: Phase 10 Governance Operations (delivered)

Phase 8 should finish the demonstrable loop:

```text
RAG answer -> user-confirmed task -> Agent/HITL -> audit trail
```

Current delivered:

- auth and group isolation
- document ingestion
- ETL and chunking
- keyword / semantic / hybrid-style retrieval foundation
- citation-grounded RAG answer
- RAG run audit
- frontend answer view with "✓ 确认任务" button
- lightweight task board v1.1 with `status=cancelled`, source RAG run inline detail, and task filters
- controlled conversation and Agent foundations: run, steps, tool registry, role-gated tools, HITL, audit trail, DeepSeek `agent_decide`, fake eval, audit hardening
- Agent frontend visibility initial page
- knowledge governance v1 foundation: archive audit, status filter, metadata display
- production safety checks: APP_ENV, JWT/cookie/database safety validation

Current Phase 8 gap:

- task `source_type` now supports `rag_run`, `conversation`, `agent_run`, and `manual` — delivered Phase 8.3
- conversation UX now includes visible citations, tool calls, and failure states — delivered Phase 8.4
- real DeepSeek Agent smoke results recorded — delivered Phase 8.1
- demo scenario scripts delivered — Phase 8.5

Phase 8 should not add new backend Agent powers. It should make existing backend capabilities visible, usable, and demonstrable.

## 5. Phase 9 Delivered / Phase 10 Delivered

Phase 9 Ontology Core v1 — delivered (2026-06-18). All planned capabilities delivered and verified against real KB (74 documents, 74 entities, 186 relations, 97 issues). See `docs/ontology-governance-demo-report.md`.

Actual findings (from real KB scan):
- 90 unresolved wikilinks (mostly `research/*` missing)
- 7 stale eval gold IDs (concepts/agent, concepts/ontology-sdk, vendors/palantir-foundry, etc.)
- KB has good entity identity quality (no duplicate titles/aliases)

Phase 10 is delivered (governance operations & demo polish — issue triage, curation demo, graph UX polish, evidence bridge, review). See `docs/phase10-planning.md` for full task breakdown.

## 6. Feature Boundaries

### Needed Capabilities

- Group-scoped document ingestion and search.
- Citation-grounded RAG answers.
- Confidence and knowledge-gap reporting.
- RAG run history and replay.
- Multi-turn conversation when it helps preserve consulting context.
- Controlled Agent tooling only when there is a real multi-step workflow.
- Lightweight task board for confirmed next steps.
- Audit trail for generated answers, retrieved citations, Agent/tool actions, and user confirmations.
- Ontology governance read model: entities, relations, validation issues, graph, and entity detail.

### Not Needed In The Near Term

- Full project management system.
- Full SaaS tenant administration.
- Billing, subscriptions, or usage plans.
- Autonomous browsing Agent.
- Automatic task creation from every answer.
- Automatic web-to-knowledge-base ingestion.
- Crawler or scheduled external monitoring.
- Kubernetes or distributed infrastructure.
- RabbitMQ/Kafka/Celery unless the current async pipeline becomes a measured bottleneck.
- Replacing deterministic backend logic with LLM decisions.
- Full manual Ontology modeling studio before governance and graph visibility.
- Graph RAG before the entity/relation read model is reliable.
- Agent auto-writing Ontology entities, relations, or actions.

## 7. Agent Boundary

Agent should be used only when the workflow has at least one of these properties:

- multiple steps
- multiple tools
- dynamic decision points
- need for audit/replay
- need for user confirmation before risky actions

Agent should not be used for deterministic work that the backend can handle directly, such as:

- permission checks
- group_id filtering
- document status filtering
- hash verification
- upload session validation
- schema validation
- wikilink parsing
- ordinary CRUD
- fixed retrieval ranking rules

### Allowed Agent Behaviors

- Suggest follow-up questions.
- Suggest lightweight tasks from answer next steps.
- Search the knowledge base through approved tools.
- Summarize retrieved evidence.
- Explain gaps and risks.
- Produce an auditable plan for a multi-step workflow.
- In later phases, propose ontology modeling drafts for user review.

### Disallowed Agent Behaviors For Now

- Create tasks without user confirmation.
- Browse the web autonomously.
- Ingest external pages into the knowledge base automatically.
- Execute destructive or cross-group actions.
- Bypass role checks or group_id boundaries.
- Write Ontology entities, relations, Object Types, Properties, Link Types, or Action Types without explicit user confirmation and audit.

## 8. Lightweight Task Board Boundary

The task board exists to turn RAG next steps into trackable work.

It is not a full PM tool.

### Minimum Task Concept

A task should represent a user-confirmed action item derived from a RAG answer, conversation, Agent run, or manual entry.

Minimum fields:

- group_id
- title
- description
- status
- source type: RAG run / conversation / Agent run / manual
- source id
- created_by
- created_at
- updated_at

Optional later fields:

- priority
- assignee display name
- due date
- linked citations
- linked ontology entity or relation

### Task Creation Rule

RAG and Agent may suggest tasks, but the user must explicitly confirm before a task is created.

This protects against noisy task creation, model overreach, and accidental workflow mutation.

## 9. Web Search Boundary

Web search is a Discovery capability, not part of the current core MVP.

The product hypothesis is:

> Controlled web search may improve low-confidence RAG answers when internal knowledge is insufficient.

Before implementation becomes core, it must be validated with a small evidence study:

- choose 5 low-confidence questions
- record current RAG answer and gaps
- test a web-search provider
- compare whether external evidence improves answer usefulness
- decide Go / No-Go based on results

Until that validation passes, web search should remain separate from the main RAG answer flow and separate from the internal ontology graph.

## 10. Success Criteria

The aligned product direction is successful if a new session can answer these questions without chat history:

- What is Semantic Lighthouse?
- What does Ontology mean in this project?
- Why is this not just RAG?
- Why is this not just Agent?
- What is the current Phase 8 workflow?
- What is Phase 9 Ontology Core v1?
- When should Agent be used?
- When should deterministic backend logic be used instead?
- Which tempting features are intentionally out of scope?

The next implementation milestone is successful if:

- Agent run/step/HITL frontend pages make existing backend capabilities visible.
- Task source_type supports `rag_run`, `conversation`, `agent_run`, and `manual` (Phase 8.3).
- Conversation UX is hardened with visible citations, tool calls, and failure states (Phase 8.4 delivered).
- Real DeepSeek Agent smoke results are recorded.
- Demo scenario scripts exist for portfolio presentation.
- Phase 9 starts from KB governance and graph visibility, not from a full modeling studio or Graph RAG.

## 11. Interview Narrative

The project story should be:

> I did not build a generic chatbot or blindly add Agent features. I first built the permission and knowledge foundations, then made RAG answers traceable through citations, confidence, gaps, and audit records. I then turned model suggestions into user-confirmed lightweight tasks, so AI output becomes reviewable work instead of untrusted automation. Agent is used only as a controlled coordination layer when the workflow is multi-step, tool-based, and auditable. The next product step is Ontology Core: making the knowledge base governable as entities, relationships, validation issues, and a graph before attempting full modeling or Graph RAG.
