# R1 Runtime Boundary Audit

Status: Delivered planning audit, 2026-06-22.
Scope: Documentation and architecture review only. No runtime code, API, migration, permission, or frontend changes.

Canonical state remains `docs/project-status.toml`.

## Purpose

R1 exists because Phase 14.5 proved the runtime chain works, but the current implementation is now dense enough that further product work should not keep accumulating inside one service file.

The goal is not to redesign the runtime. The goal is to preserve the already verified behavior while making future changes easier to review:

```text
latest package -> compiled contract context -> dataset bindings -> read query -> audit/provenance -> activation gate
```

## Current Boundary

Runtime entry points live in `src/semantic_lighthouse/routers/runtime.py`:

- `POST /groups/{group_id}/projects/{project_id}/runtime/bindings/generate`
- `GET /groups/{group_id}/projects/{project_id}/runtime/bindings`
- `POST /groups/{group_id}/projects/{project_id}/runtime/query`
- `POST /groups/{group_id}/projects/{project_id}/runtime/activate`

The implementation core lives in `src/semantic_lighthouse/services/runtime.py`:

- `_record_audit()`
- `_build_contract_context()`
- dataset path validation and CSV/XLSX readers
- binding generation
- query execution
- pilot activation

Models:

- `OntologyDatasetBinding`
- `OntologyRuntimeAudit`

Primary test coverage:

- `tests/test_project_runtime.py`
- `scripts/verify_ui.py` for end-to-end UI smoke through runtime query

## What Is Strong

- Router-level permissions are clear:
  - member+ can list bindings and query.
  - owner/admin can generate bindings and activate.
- Runtime query is intentionally constrained:
  - no SQL
  - no DSL
  - no AST
  - no LLM
  - no Graph RAG
  - equality filters only
- Runtime uses compiled package contract as the field/type source of truth.
- Query explains provenance without returning storage paths, raw data, secrets, or filter values.
- Audit is fail-closed for query and activation success paths.
- Tests cover cross-group/project isolation, path traversal, type conversion, idempotency, activation, audit persistence, and member/owner boundaries.

## Main Pressure

`src/semantic_lighthouse/services/runtime.py` is doing too much:

- contract/package lookup
- binding generation
- dataset storage path safety
- CSV/XLSX row reading
- type conversion
- query semantics
- audit writing
- activation smoke gating

This is not currently a correctness blocker. It is a maintainability and review-risk issue. Future work such as AdventureWorks, governance feedback persistence, richer query affordances, or external dataset connectors will be harder to review if all changes keep landing in this file.

## Non-Goals

R1 must not introduce:

- new runtime behavior
- new query language
- joins or relation traversal
- Graph RAG
- MCP runtime
- Agent write access
- external system connectors
- new database tables
- migration changes
- frontend redesign
- data write-back

## Recommended Refactor Shape

R1 should be behavior-preserving and extraction-first.

Suggested module boundaries:

| Module | Responsibility | Current Source |
|---|---|---|
| `services/runtime_contract.py` | latest package lookup and compiled runtime context | `_get_latest_project_package`, `_build_contract_context` |
| `services/runtime_audit.py` | sanitized audit record creation helpers | `_record_audit`, stable error code mapping |
| `services/runtime_dataset_io.py` | storage path validation, CSV/XLSX row readers | `_validate_dataset_path`, `_read_dataset_rows`, stream readers |
| `services/runtime_bindings.py` | deterministic binding generation | `generate_bindings` |
| `services/runtime_query.py` | read-only query execution and type conversion | `execute_query`, converters |
| `services/runtime_activation.py` | activation gate and smoke query orchestration | `activate_pilot` |

This split keeps the router stable and does not require API changes.

## Suggested Slices

### R1B: Contract And Audit Extraction  ✅ Delivered 2026-06-23

Move only pure-ish boundary helpers:

- latest package lookup
- contract context compilation
- audit helper
- sanitized error code mapping

Keep public service function signatures stable. No behavior change.

Verification:

- `python -m pytest tests/test_project_runtime.py -p no:cacheprovider`
- `python scripts/check_doc_alignment.py`
- `git diff --check`

### R1C: Dataset IO Extraction  ✅ Delivered 2026-06-23

Move:

- dataset path validation
- CSV row streaming
- XLSX row reading
- generic `_read_dataset_rows`

No query logic changes.

Verification:

- targeted runtime dataset/path tests in `tests/test_project_runtime.py`
- `verify_ui.py` only if imports or runtime route behavior changed in a way that could affect the UI smoke

### R1D: Query Core Extraction

Move:

- value conversion
- filter conversion
- query execution

Keep `execute_query(...)` as the stable service entry point or provide an import-compatible wrapper.

Verification:

- full `tests/test_project_runtime.py`
- `scripts/verify_ui.py`

### R1E: Binding And Activation Extraction

Move:

- `generate_bindings`
- `activate_pilot`

Do this after R1B/R1C/R1D, because activation currently calls the full query path for smoke.

Verification:

- full `tests/test_project_runtime.py`
- `scripts/verify_ui.py`
- no full project pytest unless a cross-module contract changed

## Guardrails

Every R1 implementation slice must preserve:

- route paths and request/response shapes
- group_id and project_id checks
- role requirements
- stage requirements
- audit semantics
- no storage path or raw data leakage
- compiled contract as runtime truth
- filter-before-offset-before-limit semantics
- activation smoke via the actual query path
- no Agent/MCP runtime expansion

Stop immediately if a slice requires:

- a migration
- new dependency
- runtime behavior change
- query language expansion
- frontend redesign
- external connector
- auth/group_id semantics change

## Current Decision

Proceed with R1 only as small behavior-preserving refactor slices. R1B and R1C
proved the extraction pattern is safe.

R1D remains worthwhile because query-core extraction prepares the runtime for
the next high-value product capability: limited relationship traversal over
package-declared links.

After R1D, do not keep refactoring by default. Use
`docs/palantir-ontology-four-chain-gap-analysis.md` as the route check:

- object chain: mostly in place
- permission chain: strongest current chain
- relationship chain: next gap to close through R2 relationship runtime query
- action chain: later, only with explicit HITL/audit design

R1E binding/activation extraction is optional. Run it only if R1D exposes a
concrete maintainability blocker. Do not start graph database adoption, Graph
RAG, action writeback, or Agent/MCP write paths without a separate Safety Lane
plan.
