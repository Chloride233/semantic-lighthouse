# MCP / Agent Boundary Design

**Date**: 2026-06-19
**Status**: Design only. No MCP server/client, SDK, dependency, runtime, or tool registration exists.

## 1. Strategic Role

MCP has strategic value because it can expose Semantic Lighthouse evidence,
Ontology read models, governance state, and reviewed contracts through a standard
Agent-facing interface.

MCP is an adapter at the edge of the system. It is **not** the Ontology, does not
own business rules, and cannot replace backend authorization, `group_id`
isolation, audit, HITL, or deterministic validation.

```text
enterprise Agent
  -> future MCP adapter
  -> Semantic Lighthouse application services
  -> authorization / group isolation / audit / provenance
  -> evidence and Ontology read models
```

The future adapter must call the same application services used by REST and the
existing Agent tool registry. It must not query tables directly or copy business
logic into MCP handlers.

## 2. Timeline Alignment

Phase 11.4, Phase 11.6, and Phase 12 are already delivered. This design extends
the delivered Phase 11.6 Agent boundary without reopening those phases.

The originally suggested name `Phase 12: MCP Read-only Gateway v1` cannot be
used because Phase 12 now contains Model Quality & Contract Packages. The MCP
read-only gateway is a **future candidate after Phase 13**. Its phase number will
be assigned only after the Phase 13 review.

Current work remains Phase 13 typed business contract work. This document does
not authorize MCP implementation during Phase 13.

## 3. Interface Mapping

| Future MCP capability | Kind | Existing source of truth | Boundary |
|---|---|---|---|
| `search_evidence` | Tool | group-scoped retrieval/search service | Return citation-grounded evidence with bounded result count |
| `get_entity` | Resource/tool | Ontology entity read model | Exact group-scoped lookup; no cross-group existence leak |
| `list_relations` | Resource/tool | Ontology relation read model | Paginated and bounded; preserve source/target provenance |
| `list_modeling_drafts` | Resource/tool | Modeling draft read model | Read status, payload, review metadata, and evidence only |
| `get_governance_issues` | Resource/tool | Validation issue read model | Read-only filters; no automatic triage or repair |
| `get_draft_evidence` | Resource/tool, later candidate | Draft source pointers and evidence linkage | Resolve only through checked group-scoped services |

The first runtime candidate contains the first five capabilities.
`get_draft_evidence` may follow only after the core audit and data-minimization
contract is proven.

REST routes, Agent tools, and MCP handlers are transports over shared service
logic. MCP does not call arbitrary REST endpoints through an internal HTTP loop,
and Agent tools do not call MCP to reach local backend behavior.

## 4. Identity And Authorization

- Each MCP connection/request must have an authenticated caller identity mapped
  to a real Semantic Lighthouse `user_id`.
- Allowed groups come from server-side membership records, never from model text
  or an unverified client claim.
- A client-supplied `group_id` is a selector, not authority. The server must
  validate membership and required role before every lookup.
- Where a session is bound to one group, the server injects the bound group;
  model-generated arguments cannot override it.
- Every query includes server-selected `group_id` scope. Cross-group IDs return
  the same non-disclosing behavior as current REST APIs.
- MCP does not create a second role model. It reuses owner/admin/member rules.

No anonymous MCP access, service-wide superuser context, API key shared by all
tenants, or trust in model-supplied identity is allowed.

## 5. Audit Contract

Every future invocation must record at least:

- authenticated `user_id`
- authorized `group_id`
- MCP capability name and version
- sanitized arguments or argument summary
- success/failure status
- bounded result summary, never full sensitive content by default
- citation/provenance identifiers
- error category without stack trace or secret values
- start/end timestamp and duration
- correlation/request ID

Direct MCP clients may not have an `AgentRun`, so invocation audit cannot depend
only on `AgentStep`. Runtime planning must choose a dedicated invocation audit
record or an equivalent shared audit abstraction before implementation.

## 6. Untrusted Content And Output Safety

- Retrieved documents, entity text, draft payloads, labels, and issue messages are
  untrusted data. Instructions embedded in them never affect authorization.
- Permission checks run before retrieval and before serialization, outside model
  reasoning and prompt content.
- Tool names and argument schemas are server-defined allowlists.
- Hard limits apply to rows, text length, relation depth, and evidence count.
- Outputs preserve citation/provenance while excluding secrets, tokens, cookies,
  password hashes, internal stack traces, filesystem paths, and raw SQL errors.
- Logs store summaries and identifiers instead of unrestricted tool output.
- Error responses do not reveal whether a cross-group object exists.

## 7. Read-only Gateway Candidate

If approved after Phase 13 review, MCP Read-only Gateway v1 should:

1. Implement an MCP server only; no MCP client or multi-server orchestration.
2. Reuse existing application services and server-side permission checks.
3. Start with `search_evidence`, `get_entity`, `list_relations`,
   `list_modeling_drafts`, and `get_governance_issues`.
4. Enforce caller-to-user/group mapping on every call.
5. Persist a complete invocation audit trail.
6. Test outsider denial, cross-group isolation, member access, bounded output,
   provenance retention, and non-leaking failures.
7. Avoid external CRM/ERP/BI integrations until the provider contract is proven.

Runtime work must begin with a new, explicitly approved planning document. This
design alone is not an implementation instruction.

## 8. Prohibited Behavior

MCP must not:

- create, modify, accept, reject, or publish modeling drafts
- modify Ontology entities, relations, contracts, or packages
- repair or write the external KB
- bypass owner/admin checks or query across groups
- infer authorization from prompt text or tool output
- expose secrets through output, logs, or model context
- register compiled Actions as executable tools
- execute a high-risk write without the existing backend HITL path
- implement its own confirmation state separate from backend audit

Any future write capability requires a separate Safety Lane phase. It must reuse
the existing backend transaction, authorization, idempotency, audit, and HITL
services. MCP may request that workflow; it may not approve itself.

## 9. Runtime Entry Gates

Implementation remains blocked until all are defined:

1. Authenticated transport and caller identity mapping.
2. Server-bound group selection and role policy.
3. Shared service boundaries for all five read capabilities.
4. Durable MCP invocation audit model.
5. Output limits, redaction, provenance, and error policy.
6. Prompt-injection test cases that prove permissions are deterministic.
7. Cross-group and no-existence-leak test plan.
8. Operational secret handling and deployment configuration.

Until then: design the boundary, keep runtime absent, and expose no MCP writes.
