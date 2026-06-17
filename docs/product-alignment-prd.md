# Semantic Lighthouse Product Alignment PRD

Last updated: 2026-06-17

## 1. Product Positioning

Semantic Lighthouse / 语义灯塔 is a permission-aware knowledge evidence workspace for enterprise AI transformation.

It is not a general chatbot, not a full SaaS product, and not an unrestricted autonomous Agent platform. Its core value is to help a user turn enterprise AI transformation knowledge into:

- traceable evidence
- citation-grounded answers
- confidence and knowledge-gap judgments
- reviewable next-step suggestions
- user-confirmed lightweight tasks
- auditable Agent-assisted workflows when the workflow genuinely needs multiple steps or tools

The project exists as an engineering portfolio project for AI application / RAG / Agent internship preparation. Every capability must be explainable in business terms, technical terms, risk terms, and interview terms.

## 2. Working Definition: Knowledge Evidence Workspace

A knowledge evidence workspace is a system that manages the path from knowledge to judgment to action.

For this project, that means:

```text
group-isolated knowledge -> retrieval evidence -> RAG answer -> confidence/gaps -> next steps -> confirmed task/action
```

The workspace does not merely answer questions. It should let the user inspect why an answer is credible, what evidence supports it, what is missing, and which follow-up work should be tracked.

## 3. Target Users And Scenarios

### Primary User For This Project

The project owner, using the system as a job-portfolio demonstration of enterprise RAG and Agent engineering judgment.

### Future Product-Like Users

- AI transformation consultant preparing client-facing answers.
- Enterprise knowledge operator maintaining AI transformation knowledge assets.
- Team member checking whether a recommendation is grounded in approved internal knowledge.

### Core Scenario

The near-term workflow is:

1. User logs in and enters a group workspace.
2. User uploads or imports enterprise AI transformation knowledge.
3. User asks a question.
4. System retrieves group-scoped evidence.
5. System returns answer, citations, confidence, knowledge gaps, and next steps.
6. User reviews the next steps.
7. User confirms selected next steps into lightweight tasks.
8. Future Agent workflows may help track, summarize, or coordinate these tasks, but must remain permission-aware and auditable.

## 4. Near-Term MVP

The near-term MVP is the actionable RAG loop:

```text
Ask -> Evidence -> Confidence -> Gaps -> Next Steps -> User-confirmed Task
```

The current system already has most of the first half:

- auth and group isolation
- document ingestion
- ETL and chunking
- keyword / semantic / hybrid-style retrieval foundation
- citation-grounded RAG answer
- RAG run audit
- frontend answer view
- controlled conversation and Agent foundations

The next product-aligned capability should be lightweight task handoff, not a broad Agent framework rewrite.

## 5. Feature Boundaries

### Needed Capabilities

- Group-scoped document ingestion and search.
- Citation-grounded RAG answers.
- Confidence and knowledge-gap reporting.
- RAG run history and replay.
- Multi-turn conversation when it helps preserve consulting context.
- Controlled Agent tooling only when there is a real multi-step workflow.
- Lightweight task board for confirmed next steps.
- Audit trail for generated answers, retrieved citations, and Agent/tool actions.

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

## 6. Agent Boundary

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
- ordinary CRUD
- fixed retrieval ranking rules

### Allowed Agent Behaviors

- Suggest follow-up questions.
- Suggest lightweight tasks from answer next steps.
- Search the knowledge base through approved tools.
- Summarize retrieved evidence.
- Explain gaps and risks.
- Produce an auditable plan for a multi-step workflow.

### Disallowed Agent Behaviors For Now

- Create tasks without user confirmation.
- Browse the web autonomously.
- Ingest external pages into the knowledge base automatically.
- Execute destructive or cross-group actions.
- Bypass role checks or group_id boundaries.

## 7. Lightweight Task Board Boundary

The task board exists to turn RAG next steps into trackable work.

It is not a full PM tool.

### Minimum Task Concept

A task should represent a user-confirmed action item derived from a RAG answer, conversation, or Agent run.

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

### Task Creation Rule

RAG and Agent may suggest tasks, but the user must explicitly confirm before a task is created.

This protects against noisy task creation, model overreach, and accidental workflow mutation.

## 8. Web Search Boundary

Web search is a Discovery capability, not part of the current core MVP.

The product hypothesis is:

> Controlled web search may improve low-confidence RAG answers when internal knowledge is insufficient.

Before implementation becomes core, it must be validated with a small evidence study:

- choose 5 low-confidence questions
- record current RAG answer and gaps
- test a web-search provider
- compare whether external evidence improves answer usefulness
- decide Go / No-Go based on results

Until that validation passes, web search should remain separate from the main RAG answer flow.

## 9. Success Criteria

The aligned product direction is successful if a new session can answer these questions without chat history:

- What is Semantic Lighthouse?
- What is the main workflow?
- Why is it not just a chatbot?
- Why is it not a full SaaS product?
- When should Agent be used?
- When should deterministic backend logic be used instead?
- What is the next product-aligned feature?
- Which tempting features are intentionally out of scope?

The next implementation milestone is successful if:

- RAG next steps can be reviewed by the user.
- The user can confirm selected next steps into lightweight group-scoped tasks.
- Tasks preserve source traceability to the RAG run, conversation, or Agent run.
- Non-members cannot view or mutate group tasks.
- Agent does not auto-create tasks.

## 10. Interview Narrative

The project story should be:

> I did not build a generic chatbot or blindly add Agent features. I first built the permission and knowledge foundations, then made RAG answers traceable through citations, confidence, gaps, and audit records. The next step is turning model suggestions into user-confirmed lightweight tasks, so AI output becomes reviewable work instead of untrusted automation. Agent is used only as a controlled coordination layer when the workflow is multi-step, tool-based, and auditable.
