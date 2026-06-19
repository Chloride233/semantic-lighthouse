# Ontology Agent Boundary

**Phase 11.6 — Agent-facing boundary review.**
**Status**: Delivered (2026-06-19).
**Scope**: Defines what the Agent may and may not do with ontology modeling drafts. No code changes; no new Agent tools.

---

## 1. Current Runtime Boundary

The Agent can only execute tools explicitly registered in `AGENT_TOOLS`
(`src/semantic_lighthouse/services/agent_orchestrator.py`). As of Phase 11
completion, the tool list is:

| Tool | Role | Risky |
|------|------|-------|
| `search_knowledge_base` | member | no |
| `list_documents` | member | no |
| `archive_document` | admin | yes |

The Agent does **not** call arbitrary REST endpoints. It routes every action
through `_execute_tool()` which matches against `AGENT_TOOLS` by name and
returns an error for unregistered tools.

As of this writing, the Agent **cannot** read, create, generate, review,
modify, or publish ontology modeling drafts. No ontology draft tool exists
in `AGENT_TOOLS`. The orchestrator has zero imports from
`ontology_drafts` or `OntologyModelingDraft`.

Draft creation (`POST /ontology/drafts`), generation (`POST /ontology/drafts/generate`),
and review (`POST /ontology/drafts/{id}/review`, `POST /ontology/drafts/review-batch`)
are REST endpoints with role checks (`owner`/`admin`), not Agent tools.

---

## 2. Allowed Behavior

The Agent **may**, through existing tools:

- Search the knowledge base and retrieve evidence that could inform a
  modeling proposal.
- In natural-language responses (conversation, plan, final answer),
  suggest non-persisted Object Type / Property / Link Type / Action Type
  candidates.
- In the future, a read-only `list_ontology_drafts` tool could be evaluated
  as a separate feature with its own planning, tests, and audit. This is
  **not** implemented in Phase 11.

All generated suggestions are **non-persistent text only**. They do not
create database records, do not write to the external KB, and do not
bypass any permission check.

---

## 3. Disallowed Behavior

The Agent **must NOT** — now or in any future Phase 11 work:

- Register `create_draft`, `generate_drafts`, `review_draft`,
  `batch_review_drafts`, or `publish_draft` as an Agent tool.
- Auto-persist a natural-language suggestion as an `OntologyModelingDraft`
  record.
- Accept or reject a draft (`accepted` / `rejected` status).
- Promote an accepted draft to production schema.
- Modify the external KB (`F:\ontology-kb\knowledge-graph`).
- Bypass `group_id` scoping, role checks, HITL confirmation, or audit
  event recording for any ontology operation.

---

## 4. Future Gate

Any future Agent write capability touching ontology drafts **must** be a
separate, explicitly planned feature meeting **all** of these conditions:

1. Clear business scenario (not speculative generality).
2. Group-scoped permission check (same group_id invariant).
3. User confirmation (HITL gate, not auto-execute).
4. Independent audit event (separate `AgentStep` with full detail).
5. Idempotency and failure-recovery story.
6. Does **not** write directly to external KB or production schema.

Until these conditions are met, Agent write access to ontology modeling
drafts remains **prohibited**.
