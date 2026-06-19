# Phase 13 Planning — Typed Business Ontology Contract & Manufacturing Pilot v1

**Date**: 2026-06-19
**Status**: 13.1 complete (profile spec defined), 13.2–13.6 PLANNED — no implementation has started.

---

## Phase 13 Goal

Advance the Phase 12 "audit-type model package" into a **deterministically validated, application-readable business Ontology contract with stable type definitions** — without publishing to production, storing object instances, executing Actions, or generating an SDK.

Phase 13 bridges the gap from an internal, audit-heavy snapshot toward a **typed contract that an application or Agent could safely consume**.

---

## 1. Current Breakpoint

### 1.1 What Phase 12 Proved

| Capability | Evidence |
|---|---|
| Drafts carry source evidence (entity_id, relation_id, issue_id, rag_run_id). | 76 drafts from real KB, all have source pointers. |
| Human review produces audit records (reviewed_by, reviewed_at, review_note). | Phase 11.4 review workflow, one-time audit finality. |
| Accepted-only packages are buildable with content hash and version. | Phase 12.3b builder, idempotent rebuild. |
| Packages are quality-gated, dependency-gated, hash-stable, and exportable. | 434 non-E2E tests, 69 Phase 12 tests. |
| Action drafts carry declarative role, confirmation, and evidence boundaries. | Phase 12.5 action_contract, deterministic defaults. |

### 1.2 What Phase 12 Has Not Yet Proven

| Gap | Why it matters |
|---|---|
| Packages cannot express real business Object Types (Equipment, WorkOrder, Customer, Order). | Current packages model knowledge assets (Concept, Vendor, Product), not enterprise business objects. |
| Properties lack stable business value_type, required, and primary_key declarations. | Current `observed_value_types` is a heuristic list from frontmatter — not a typed contract. |
| Links lack business names and cardinality. | Current links are wikilink-extracted: `relation_type=wikilink`, no cardinality, no business semantics. |
| Actions lack target object, parameters, and declared effects. | Current actions are governance-only — no target object type, no parameter schema, no effects declaration. |
| Applications cannot consume a stable, audit-noise-free contract manifest. | Current export is raw `contract_json` with `reviewed_at`, `review_note`, `draft_id` — useful for audit, not for application consumption. |
| An Agent cannot safely discover capabilities from a contract. | No stable API-level contract that an Agent could introspect to understand available object types, property schemas, link traversals, or action parameters. |

### 1.3 The Critical Distinction: knowledge_meta vs business_v1

**This is the single most important design judgment in Phase 13.**

```
knowledge_meta         ≠    business_v1
─────────────────          ─────────────
Concept, Vendor,           Equipment, WorkOrder,
Product, Methodology,      Customer, Order,
Case, FAQ, Person,         Supplier, Project,
Proposal, Research         Alert, Asset
```

- **knowledge_meta** is the Phase 9–12 draft source. It models the knowledge asset taxonomy — what kind of document is this? Who wrote it? What concepts does it relate to? These are **metadata about knowledge**, not business entities in an enterprise.
- **business_v1** is the target enterprise Ontology. It models **real business objects** — equipment on a factory floor, work orders in a maintenance system, customers in a CRM, orders in an ERP.

**Rule: knowledge_meta packages MUST NOT be automatically upgraded into business_v1 packages.** The two profiles serve different purposes and must be validated by different rules. A knowledge_meta package missing `value_type` is correct — knowledge properties describe document metadata. A business_v1 package missing `value_type` is broken — business properties must be typed for application consumption.

---

## 2. Phase 13 Scope

### 13.1 Business Contract Profile Specification ✅

**Goal**: Define the `business_v1` contract profile as a specification document, distinct from the Phase 12 audit package format.

**Deliverables**:
- `docs/phase13-business-contract-spec.md` — normative specification of the business_v1 contract profile. **Delivered 2026-06-19.**
- Declare the relationship: a business_v1 contract is **derived from** a Phase 12 immutable package, but is a **separate artifact** with its own identity, hash, and validation rules.
- Define the profile identifier: `contract_profile: business_v1` as a **payload field** on each draft, not a database column or package-root field.
- Define the distinction between `raw audit contract` (Phase 12 `contract_json`) and `compiled business manifest` (Phase 13 output).
- Profile detection is by `payload.contract_profile` only — NOT by name patterns (Concept, Vendor, Product, etc.).

**Non-goals**:
- Do not modify the Phase 12 package schema, builder, or export API.
- Do not define additional profiles (no `knowledge_meta`, `hybrid`, `v2`).
- Do not generate OpenAPI, JSON Schema, or GraphQL artifacts.

**Tests**: None. 13.1 is a documentation-only slice — the profile spec is the deliverable. No pytest, no API, no migration.

**Risk controlled**: Diffs are distinguishable — a missing `contract_profile` causes validation failure; knowledge_meta packages are not wrongly identified by name heuristics.

---

### 13.2 Deterministic Business Contract Validator

**Goal**: Validate that a `business_v1` drafted package satisfies minimum type, structure, and completeness rules before compilation.

**Core rule**: The validator is **deterministic** — no LLM, no type inference from field values, no modification of drafts. It returns structured errors/warnings. It never auto-corrects.

**Validation rules** (minimum):

| Code | Severity | Rule |
|------|----------|------|
| `missing_primary_key` | ERROR | Object Type must declare exactly one `primary_key` property. |
| `missing_value_type` | ERROR | Every property must declare a `value_type` from the v1 allowed set. |
| `invalid_value_type` | ERROR | `value_type` not in v1 allowed set. |
| `missing_cardinality` | ERROR | Every link type must declare a `cardinality` from the v1 allowed set. |
| `invalid_cardinality` | ERROR | `cardinality` not in v1 allowed set. |
| `missing_target_object_type` | ERROR | Every action must declare a `target_object_type`. |
| `missing_action_parameters` | WARN | Action has no parameters — allowed but flagged for review. |
| `undeclared_parameter_value_type` | ERROR | Action parameter `value_type` not in v1 allowed set. |
| `missing_required_role` | ERROR | Action must declare `required_role` from v1 role set. |
| `link_source_not_in_package` | ERROR | Link `source_object_type` not present in package object_types. |
| `link_target_not_in_package` | ERROR | Link `target_object_type` not present in package object_types. |
| `action_target_not_in_package` | ERROR | Action `target_object_type` not present in package object_types. |
| `property_object_type_not_in_package` | ERROR | Property `object_type` not present in package object_types. |
| `contract_profile_mismatch` | ERROR | Draft `payload.contract_profile` missing or not exactly `"business_v1"`. Detection is by payload field only — NOT by api_name patterns. |
| `duplicate_api_name` | ERROR | Two entities of same type share `api_name`. |
| `missing_display_name` | WARN | Entity has no `display_name` — defaults to `api_name`. |

**Non-goals**:
- No modification of draft status, payload, or review metadata.
- No creation of new drafts or packages.
- No LLM-based type inference.
- No validation of knowledge_meta packages against business_v1 rules.

**Tests**: 5–8 parametrized tests **total** (not per error code). Organized by category: profile check, object type validation, property validation, link validation, action validation. No API, no migration.

**Risk controlled**: A structurally invalid business_v1 package cannot proceed to compilation.

---

### 13.3 Business Contract Compiler

**Goal**: Derive a stable, application-consumable `compiled business manifest` from a validated business_v1 immutable package.

**Input**: An existing Phase 12 `OntologyModelPackage` whose `contract_json` satisfies business_v1 validation (13.2).
**Output**: A compiled manifest dict — not persisted, not published, not written to external systems.

**Compilation rules**:

1. **Remove audit noise**: Strip `reviewed_at`, `review_note`, `draft_id`, `source_entity_id`, `source_relation_id`, `source_issue_id`, `source_rag_run_id`, `evidence_refs` from each entity entry.
2. **Sort deterministically**: Object types, properties, link types, action types sorted by `api_name`. Properties within an object type sorted by `api_name`. Parameters within an action sorted by `name`.
3. **Compute semantic_hash**: SHA-256 of the canonical compiled JSON (sort_keys, ensure_ascii=False, fixed separators). The hash covers ONLY the four business definition arrays — NOT `manifest`, `provenance`, or any top-level metadata.
4. **Preserve provenance**: Include `source_package_id`, `source_package_version`, `source_content_hash` as a `provenance` block — these identify which immutable audit package produced this manifest, but do not participate in `semantic_hash`.
5. **Add manifest metadata**: `contract_profile: business_v1`, `schema_version: 1.0`, `semantic_hash`. No `compiled_at` — timestamps break hash stability.

**Compiled manifest structure**:

```json
{
  "manifest": {
    "contract_profile": "business_v1",
    "schema_version": "1.0",
    "semantic_hash": "sha256:…"
  },
  "provenance": {
    "source_package_id": "uuid",
    "source_package_version": 1,
    "source_content_hash": "sha256:…"
  },
  "object_types": [],
  "properties": [],
  "link_types": [],
  "action_types": []
}
```

**Non-goals**:
- No persistence (no new table, no migration).
- No publishing to external systems.
- No TypeScript/Java/Python client generation.
- No MCP resource or tool registration.
- No Object CRUD API derivation.
- No Action execution.
- No write-back to the Phase 12 package (immutable).

**Tests**: 5–8 compiler tests covering hash stability, audit noise removal, provenance correctness, deterministic sort, empty package handling. No API, no migration.

**Cross-database hash independence**: The Phase 12 `content_hash` may differ across database instances (different draft UUIDs produce different contract_json), but the `semantic_hash` MUST be identical for the same business definitions regardless of database. The two hashes cover different content and serve different purposes.

**Risk controlled**: The same business_v1 package always produces the same semantic_hash, independent of when or by whom it was compiled.

---

### 13.4 Read-Only Contract Export API

**Goal**: Expose the compiled business manifest through a read-only API endpoint.

**Endpoint**: `GET /groups/{group_id}/ontology/packages/{package_id}/contract`

**Permissions**:
- `member+` can read.
- `owner/admin` does not gain execution capability from the higher role — this endpoint is read-only regardless of role.
- Outsider → 403.
- Cross-group package → 404.

**Behavior**:
- If the package's `contract_json` does not satisfy business_v1 validation → `422 Unprocessable Entity` with structured validation errors (from 13.2). The endpoint does NOT compile invalid packages.
- If the package contains any draft missing `payload.contract_profile: business_v1` → `422` with `contract_profile_mismatch` errors.
- On success → `200` with compiled manifest and `Content-Type: application/json`.

**Non-goals**:
- No PATCH, PUT, DELETE, POST.
- No `activate`, `publish`, or `execute`.
- No query parameters beyond the package ID.
- No batch export, no streaming, no pagination.
- No `?format=openapi` or `?format=typescript`.
- No write to external systems.

**Tests**: 5–8 API tests covering member read, outsider 403, cross-group 404, contract_profile_mismatch 422, invalid business_v1 422, success 200 with hash stability, no-mutate 405. No migration.

**Risk controlled**: Applications and Agents can only consume contracts that have passed deterministic validation.

---

### 13.5 Manufacturing Pilot v1

**Goal**: Build a minimal, hand-crafted business_v1 model for a manufacturing scenario and demonstrate the full Phase 13 pipeline end-to-end — without creating real object instances, connecting to ERP/MES/PLC, or executing Actions.

**Pilot boundary**:
- **Independent demo group** — does not share data with the Phase 12 knowledge_meta demo group.
- **Hand-crafted drafts** — NOT generated from existing ontology entities (the knowledge_meta KB has no Equipment/WorkOrder entities).
- **All drafts must have** source evidence (explicit `evidence_refs` pointing to the manufacturing pilot proposal and relevant ontology KB documents), human review (accepted status), and package audit.

**Minimum business model**:

| Entity | api_name | Key Properties |
|--------|----------|----------------|
| Equipment | `equipment` | `equipment_id` (string, primary_key, required), `name` (string, required), `status` (string, required) |
| WorkOrder | `work_order` | `work_order_id` (string, primary_key, required), `title` (string, required), `status` (string, required) |

| Link | api_name | cardinality |
|------|----------|-------------|
| Equipment.workOrders → WorkOrder | `equipment_work_orders` | one_to_many |
| WorkOrder.equipment → Equipment | `work_order_equipment` | many_to_one |

| Action | api_name | target | Key Parameters |
|--------|----------|--------|----------------|
| CreateWorkOrder | `create_work_order` | WorkOrder | `title` (string, required), `equipment_id` (string, required), `priority` (string, required), `description` (string) |

**Demo flow** (script: `scripts/run_manufacturing_pilot_demo.py`):

1. Create demo group.
2. Manually POST modeling drafts: 2 object_type + 6 property + 2 link_type + 1 action_type = 11 drafts.
3. Owner/admin reviews and accepts all 11 drafts.
4. Build immutable package (Phase 12.3b).
5. Validate business_v1 contract (Phase 13.2) → expect PASS or WARN.
6. Compile business manifest (Phase 13.3) → verify semantic_hash.
7. Export via API (Phase 13.4) → verify JSON shape.
8. Rebuild package → same semantic_hash (idempotent).
9. Verify audit chain: all drafts have reviewed_by/reviewed_at, package has created_by/created_at, manifest has provenance.

**Non-goals**:
- No object instance storage (no `equipment` or `work_orders` table).
- No ERP, MES, or PLC integration.
- No `CreateWorkOrder` execution.
- No Functions runtime.
- No OSDK code generation.
- No MCP/Agent tool registration.
- No Graph RAG on the manufacturing model.
- No knowledge_meta to business_v1 auto-conversion.
- No generic "business object building wizard."

**Tests**: 5–8 demo tests verifying counts, hash stability, audit chain, cross-group isolation. No migration.

**Risk controlled**: The manufacturing pilot proves the business_v1 pipeline works on real-world shaped data without overbuilding a generic modeling framework for manufacturing.

---

### 13.6 Phase 13 Review

**Goal**: Verify all Phase 13 slices end-to-end, document findings, and decide the next phase direction.

**Review checklist**:
- [ ] business_v1 validator is deterministic — same input always produces same errors/warnings.
- [ ] semantic_hash is stable — same business content → same hash regardless of package metadata.
- [ ] semantic_hash is different — different business content → different hash.
- [ ] knowledge_meta packages are rejected by business_v1 validation.
- [ ] Group isolation: compiled manifest only returns data for the group that owns the package.
- [ ] Permission: member read, outsider 403, cross-group 404.
- [ ] Evidence chain: business_v1 manifest provenance points to immutable source package.
- [ ] Audit chain: compiled manifest excludes audit noise, manifest metadata is separate from provenance.
- [ ] No mutation: Phase 12 packages unchanged. No new tables. No new migrations.
- [ ] Manufacturing pilot reproducibility: script produces identical results on re-run (idempotent).

**Decision gates at review**:
- **Go to Phase 14 Object Runtime Read Layer**: If business_v1 contracts are stable, the next logical step is reading real business objects through the contract.
- **Go to Phase 14 SDK Generation**: If contract consumption patterns are clear, generate typed clients.
- **Stay in contract refinement**: If type definitions, cardinality, or validation rules need iteration.
- **None of the above is pre-committed.** Phase 13 review decides; this plan only defines options.

**Tests**: Full non-E2E pytest regression (expect ~434 → ~450–470 after Phase 13 slices). No E2E, no Playwright, no verify_ui.

---

## 3. business_v1 Contract Field Definitions

### 3.1 Object Type

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `contract_profile` | string | yes | Literal `business_v1`, validated at compile time. |
| `api_name` | string | yes | Machine-readable identifier, snake_case. Unique within package. |
| `display_name` | string | yes | Human-readable label. |
| `primary_key` | string | yes | Must reference an `api_name` in this object's properties. |
| `description` | string | yes | Business definition of this object type. |

**Constraints**:
- `api_name` unique within package object_types.
- `primary_key` must exist in the object's property list.
- No `icon`, `color`, `ui_metadata`, `title_property`, or `subtitle_property` in v1.

### 3.2 Property

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `object_type` | string | yes | `api_name` of the parent Object Type (must exist in package). |
| `api_name` | string | yes | Machine-readable identifier, snake_case. |
| `display_name` | string | yes | Human-readable label. |
| `value_type` | string | yes | Must be in v1 allowed set. |
| `required` | boolean | yes | Default false. |
| `description` | string | yes | Business definition of this property. |

**value_type v1 allowed set** (closed enumeration):

| value_type | JSON representation | Example |
|---|---|---|
| `string` | string | `"CNC-Mill-03"` |
| `integer` | number (no decimal) | `42` |
| `number` | number (float) | `3.14` |
| `boolean` | boolean | `true` |
| `date` | string (ISO 8601 date) | `"2026-06-19"` |
| `datetime` | string (ISO 8601 datetime) | `"2026-06-19T10:30:00Z"` |
| `string_list` | array of strings | `["tag_a", "tag_b"]` |

**Explicitly NOT in v1**:
- Nested objects or struct types.
- Union types (`string \| number`).
- Generics (`Array<T>`, `Optional<T>`).
- Expression DSL or computed value types.
- Custom code types (enum references, foreign type references).
- `MediaReference`, `TimeSeries`, `Geospatial` — these are Palantir-specific and not needed for v1.

### 3.3 Link Type

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `api_name` | string | yes | Machine-readable identifier, snake_case. |
| `display_name` | string | yes | Human-readable label. |
| `source_object_type` | string | yes | `api_name` of source Object Type (must exist in package). |
| `target_object_type` | string | yes | `api_name` of target Object Type (must exist in package). |
| `cardinality` | string | yes | Must be in v1 allowed set. |
| `description` | string | yes | Business definition of this link. |

**cardinality v1 allowed set** (closed enumeration):

| cardinality | Meaning |
|---|---|
| `one_to_one` | Each source object links to exactly one target object. |
| `one_to_many` | Each source object links to zero or more target objects. |
| `many_to_one` | Many source objects link to the same target object. |
| `many_to_many` | Source and target objects can link arbitrarily. |

**Constraints**:
- `source_object_type` and `target_object_type` must exist in the package's `object_types`.
- Self-referential links allowed (`source_object_type == target_object_type`).
- No link properties in v1 (no `weight`, `since`, `context` on the edge).

### 3.4 Action Type

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `api_name` | string | yes | Machine-readable identifier, snake_case. |
| `display_name` | string | yes | Human-readable label. |
| `target_object_type` | string | yes | `api_name` of the Object Type this action operates on. |
| `parameters` | list[ActionParameter] | yes | May be empty list. |
| `declared_effects` | list[string] | yes | Text declarations only — no executable binding. |
| `required_role` | string | yes | `admin` \| `owner` \| `member`. |
| `confirmation_requirement` | string | yes | `always` \| `conditional` \| `none`. |
| `evidence_requirement` | list[string] | yes | Non-empty list of trimmed strings. |

**ActionParameter**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | yes | Parameter name, snake_case. |
| `value_type` | string | yes | Must be in v1 value_type allowed set. |
| `required` | boolean | yes | Default false. |

**Constraints**:
- `target_object_type` must exist in the package's `object_types`.
- `value_type` must be in v1 allowed set.
- `required_role` must be one of `admin | owner | member`.
- `confirmation_requirement` must be one of `always | conditional | none`.
- `declared_effects` are **text strings only** — they describe what the action intends to do. They are NOT bound to database operations, function calls, API endpoints, or Agent tools. A future phase may add effect binding; v1 is declaration-only.
- `evidence_requirement` must be a non-empty list of trimmed strings.

**Explicitly NOT in v1**:
- `declared_effects` executable bindings.
- Parameter validation rules (min/max, regex, enum constraints).
- Async action flag.
- Action chaining or workflow composition.
- Return type declaration.
- Side-effect declarations beyond `declared_effects` text.

---

## 4. Compiled Manifest Boundary

The compiled business manifest is the **application-consumption artifact** derived from an immutable Phase 12 package. It is:

- **Stable**: Same business content → same `semantic_hash`. Independent of draft IDs, review timestamps, creator identity, or environment.
- **Minimal**: Contains only the type definitions an application needs. No audit fields, no evidence pointers, no draft lifecycle metadata.
- **Sorted**: All arrays deterministically ordered by `api_name`.
- **Verified**: Only produced after passing deterministic business_v1 validation (13.2).

It is NOT:

- A Phase 12 package replacement. The source package remains the immutable audit artifact.
- A publishable "production Ontology." It is an internal contract artifact.
- A code-generation source (yet). It is a stable JSON manifest that future tooling could consume.
- An MCP resource or tool registration. Agent integration is deferred to a future phase.
- A CRUD API. Object instances are not stored, Actions are not executed.

---

## 5. Explicit Non-Goals

Phase 13 does **NOT** do any of the following:

| Non-goal | Why deferred |
|---|---|
| Frontend or modeling UI | Phase 11.5 UI remains deferred to Kimi. No static/js, CSS, or HTML changes. |
| Business object instance tables | No `equipment` or `work_orders` database table. |
| Package activate/publish | Packages remain app-internal snapshots. |
| Action execution | `CreateWorkOrder` is declared, never invoked. |
| Functions runtime | No `predictFailure` or `calculateRiskScore` execution. |
| OSDK / code generation | No TypeScript, Java, or Python client generation. |
| MCP / Agent tool registration | No MCP resources or tools derived from contracts. |
| Graph RAG | No graph traversal on business_v1 links. |
| ERP / MES / PLC integration | No external system connections. |
| External KB modification | `F:\ontology-kb\knowledge-graph` unchanged. |
| knowledge_meta → business_v1 auto-conversion | Explicitly blocked at the validator level (13.2). |
| Multi-profile package selector | Only `business_v1` profile; no hybrid or multi-profile packages. |
| Full JSON Schema / OpenAPI generation | Only the compiled manifest JSON structure; no schema vocabulary. |
| Generic manufacturing framework | Exactly Equipment + WorkOrder + CreateWorkOrder; no extensible modeling DSL. |

---

## 6. Risk and Acceptance

### 6.1 Identified Risks

| Risk | Likelihood | Severity | Mitigation |
|------|-----------|----------|------------|
| Drafts missing `contract_profile: business_v1` enter business_v1 validation | Medium | HIGH | Validator error code `contract_profile_mismatch` blocks compilation for every item missing the profile field. 13.2 test explicitly verifies rejection. |
| Raw package hash confused with semantic_hash | Medium | MEDIUM | Two separate fields: `source_content_hash` in provenance, `semantic_hash` in manifest. 13.3 tests verify independence. |
| Hand-crafted payload as arbitrary dict causes contract instability | Medium | MEDIUM | business_v1 validator enforces required fields, allowed value_type set, and cross-reference consistency BEFORE compilation. |
| Action `declared_effects` mistaken for executable behavior | Medium | MEDIUM | `declared_effects` are string arrays with no executable binding. API docs + test names explicitly state "declaration-only." |
| Compiler bypasses group_id and package read permission | Low | HIGH | 13.4 API uses existing `get_membership_or_404` + package group_id check. Tests verify cross-group 404. |
| Manufacturing pilot overbuilds into a generic modeling framework | Low | MEDIUM | Pilot scope is hard-coded: exactly 2 OT + 6 property + 2 link + 1 action. No configuration-driven model builder. No "add your own Object Type" API. |

### 6.2 Slice Control Rules

Each Phase 13.x slice follows these constraints:

- **Single behavior** — one service, one test file, one concern.
- **5–8 related tests** per slice — enough to cover success, failure, isolation, and idempotency paths.
- **No full pytest** per slice — only the slice's test file plus any directly affected existing tests.
- **Phase 13.6 review** runs the full non-E2E pytest suite once, at the end.
- **No frontend work** — zero static/js, CSS, HTML changes.
- **No framework or DSL** — no new dependency, no configuration language, no plugin system.
- **No new migration** — Phase 13 does not add database tables unless 13.4 requires one (which it should not; compiled manifests are not persisted).

### 6.3 Phase Acceptance Criteria

Phase 13 is complete when:

1. business_v1 profile spec is written and reviewed.
2. Validator catches all defined error/warning conditions deterministically.
3. Non-business_v1 packages are rejected with `contract_profile_mismatch`.
4. Compiler produces stable semantic_hash across identical inputs.
5. Compiled manifest excludes audit noise and preserves provenance.
6. Export API enforces group isolation and permissions.
7. Manufacturing pilot demonstrates the full pipeline end-to-end.
8. Phase 13.6 review verifies all boundaries and hash stability.
9. Full non-E2E pytest passes (~450–470 expected after all slices).
10. Ruff clean, git diff clean, no new migrations.

---

## 7. Post-Phase 13 Options (Not Pre-Committed)

Phase 13 review (13.6) will decide the next direction. This section lists options for context only — **none is committed or implied**.

| Option | Description | Gating Condition |
|--------|-------------|-----------------|
| Phase 14a: Object Runtime Read Layer | Store business object instances through the contract. Read API with contract-driven validation. | business_v1 contract is type-stable and validated. |
| Phase 14b: OSDK / Client Generation | Generate TypeScript/Java/Python typed clients from compiled manifest. | Compiled manifest structure is stable and consumer patterns are understood. |
| Phase 14c: Contract Refinement | Add value_type constraints, enum types, parameter validation rules, or multi-profile support. | Phase 13 review finds gaps in type expressiveness or validation depth. |
| Defer to Phase 11.5 UI | Start Kimi frontend refactor with modeling panel. | Contract backend is sufficiently stable for UI work to begin. |

**None of these options is decided in Phase 13.** The review will assess what Phase 13 proved and what the next highest-value increment is.

---

## 8. Implementation Sequence

```
13.1 Contract Profile Spec  ──→  13.2 Business Contract Validator
                                        │
                                        ▼
13.3 Business Contract Compiler  ←──  (validated package)
        │
        ▼
13.4 Read-Only Contract Export API
        │
        ▼
13.5 Manufacturing Pilot v1  (uses all of 13.2–13.4)
        │
        ▼
13.6 Phase 13 Review  (full suite, boundary verification)
```

- 13.1 is a documentation-only slice — defines the spec before code.
- 13.2 and 13.3 can partially overlap: validator defines the rules, compiler consumes validated output.
- 13.4 depends on 13.3 (needs the compiler to produce output).
- 13.5 depends on all of 13.2–13.4 (uses validator → compiler → API in sequence).
- 13.6 is the final gate.

---

## 9. Verification Commands (per slice)

```powershell
# Slice-level (13.1–13.5)
.\.venv\Scripts\python -m pytest tests/test_business_contract_{slice}.py -p no:cacheprovider

# Phase boundary (13.6 only)
.\.venv\Scripts\python -m pytest -p no:cacheprovider --basetemp=.tmp\pytest-phase13

# Lint (changed files only per slice; full at 13.6)
.\.venv\Scripts\python -m ruff check src tests
```

---

## 10. Related Documents

- `docs/phase12-planning.md` — Phase 12 delivered packages, quality gates, action contracts.
- `docs/phase12-review.md` — Phase 12 review findings.
- `docs/product-alignment-prd.md` — Product boundary; Ontology definition.
- `docs/project-roadmap.md` — Phase 13 will be added as PLANNED.
- `F:\ontology-kb\knowledge-graph\concepts\object-type.md` — Reference: Object Type semantics.
- `F:\ontology-kb\knowledge-graph\concepts\property.md` — Reference: Property types and semantics.
- `F:\ontology-kb\knowledge-graph\concepts\link-type.md` — Reference: Link Type cardinality and semantics.
- `F:\ontology-kb\knowledge-graph\concepts\action-type.md` — Reference: Action Type structure (parameters, validation, effects).
- `F:\ontology-kb\knowledge-graph\proposals\manufacturing-mid-size-ontology-pilot.md` — Reference: Manufacturing pilot target model.
