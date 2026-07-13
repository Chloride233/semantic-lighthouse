# Phase 2 Controlled Agent Security Report

## Result

Evidence Roadmap Phase 2 validates the controlled Agent and security boundaries
from GitHub Issue #4 with 12 deterministic API-level attack and misuse cases.
All 12 cases pass with the fake provider and require no external credentials.

Run the regression gate from the repository root:

```bash
.venv/bin/python scripts/run_phase2_security_gate.py
```

The gate exits non-zero when any Phase 2 security case fails.

## Closeout Verification

- Phase 2 security gate: 12 passed
- Related Agent, audit, and task regression: 71 passed
- RAG regression: 49 passed
- Browser E2E with system Chrome: 18 passed
- Full regression: 1,135 passed, 3 skipped
- Ruff: clean across `src` and `tests`
- Documentation alignment: passed across all seven entry documents
- Implementation commit: `ed57b05`
- Closeout commit: `f40ca6f`

## Attack And Misuse Evidence

| Category | Cases | Result | Proved control |
|---|---:|---:|---|
| Prompt injection | 2 | 2/2 passed | Injected goals cannot skip HITL; injected retrieved instructions cannot escape the tool registry |
| Invalid tool use | 2 | 2/2 passed | Unknown tools and missing required arguments produce failed audit steps without writes |
| Authorization and state | 2 | 2/2 passed | Member writes fail before confirmation; pending confirmation blocks further execution with HTTP 409 |
| Cross-group isolation | 3 | 3/3 passed | Foreign runs cannot be read, executed, or confirmed; foreign document content is absent from Agent search |
| HITL and audit | 3 | 3/3 passed | Authorized writes pause; rejection records actor and preserves data; confirmation records actor/time/tool and document archive audit |
| **Total** | **12** | **12/12 passed** | **All five Issue #4 acceptance items have deterministic evidence** |

## Security Corrections

Two backend controls were tightened:

1. Tool registration and the authenticated user's server-derived membership
   role are checked before a risky action can enter HITL. Unauthorized writes
   create a failed Agent tool step and never present a misleading confirmation.
2. A run in `awaiting_confirmation` rejects `/execute` with HTTP 409. Only the
   authenticated run owner's `/respond` request can resolve the pending action.

Confirmation still re-derives membership from server-side context, and the tool
execution layer checks the role and group-scoped document query again before
calling the deterministic document lifecycle service.

## Audit Evidence

For a confirmed archive, the regression suite verifies:

- the original pending `ask_user` step and its tool arguments
- a confirmation response step with authenticated `user_id` and `responded_at`
- a separate completed `tool_call` step
- document `archived_by`, `archived_at`, and `archive_reason`

For rejection, the suite verifies the authenticated actor and response time,
preserves the original pending request, and proves that the document remains
unchanged.

Unknown, malformed, and unauthorized tool requests retain the proposed tool and
arguments in a failed step with an explicit error message.

## Agent Versus Fixed Workflow Boundary

The Agent may choose among registered tools, coordinate bounded multi-step read
work, and request user decisions. It does not own authorization, group scope,
state transitions, CRUD, or audit writes.

Deterministic backend routes and services own:

- authenticated membership and role derivation
- `group_id` filtering and run ownership checks
- tool registry validation and permission enforcement
- HITL state transitions
- document lifecycle writes and audit fields

A predictable one-step operation should use its direct backend workflow. Agent
output is untrusted input to these controls and never authorizes a database
write by itself.

## Claim Boundary And Residual Risk

This phase proves deterministic backend containment when fake-provider output is
malicious, malformed, or unauthorized. It does not prove that a real hosted
model will recognize or ignore prompt injection. Real-provider adversarial
behavior remains a follow-up validation item.

The tests use isolated SQLite data and do not exercise production deployment,
provider availability, or concurrent confirmation requests. No runtime MCP
server, client, SDK, resource, or tool is introduced.

## Resume-Ready Statement

Built a 12-case controlled Agent security regression gate covering prompt
injection, invalid tool calls, unauthorized writes, cross-group isolation,
server-derived RBAC, HITL, and audit evidence; hardened tool authorization to
reject member writes before confirmation and locked pending runs against repeat
execution; achieved 12/12 deterministic attack and misuse cases passing with a
single offline command and no external provider key.
