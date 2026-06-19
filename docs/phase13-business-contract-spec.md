# Business Ontology Contract Profile — business_v1

**Date**: 2026-06-19
**Status**: Defined (Phase 13.1 complete)
**Audience**: Phase 13.2 validator authors, 13.3 compiler authors, 13.4 API authors, 13.5 pilot authors.

---

## 1. Profile Identity

### 1.1 contract_profile

Every business_v1 draft MUST declare in its `payload`:

```json
{
  "contract_profile": "business_v1"
}
```

- `contract_profile` is a **payload field** on each individual draft. It is NOT a database column, NOT a package-level metadata field, and NOT a new field on `OntologyModelingDraft` or `OntologyModelPackage`.
- The value is the literal string `"business_v1"` — case-sensitive, no whitespace, no aliases.
- This field does NOT modify the Phase 12 package root structure. The `contract_json` shape (`schema_version`, `object_types`, `properties`, `link_types`, `action_types`) is unchanged.

### 1.2 Profile Detection

A draft belongs to `business_v1` if and only if `payload.contract_profile == "business_v1"`.

A draft does NOT belong to `business_v1` if:
- `payload.contract_profile` is missing.
- `payload.contract_profile` is not a string.
- `payload.contract_profile` is a string but not exactly `"business_v1"`.

**Explicit rule: do NOT detect business_v1 by name patterns.** The validator MUST NOT inspect `api_name`, `display_name`, or `name` to determine whether something is "business" or "knowledge_meta." Names like `Concept`, `Vendor`, `Product`, `Person`, `Methodology`, `Case`, `FAQ`, `Proposal`, `Research` are NOT used as detection signals. Profile membership is determined solely by the `contract_profile` payload field.

### 1.3 contract_profile_mismatch

If a package contains any item whose `payload.contract_profile` is absent or not exactly `"business_v1"`, the validator returns:

```json
{
  "code": "contract_profile_mismatch",
  "severity": "error",
  "message": "Draft payload.contract_profile must be 'business_v1'",
  "draft_id": "<draft_id>"
}
```

A package where ALL items lack `contract_profile: business_v1` produces one `contract_profile_mismatch` per item — the validator does not treat the package as a different profile, it simply fails validation.

The error code `contract_profile_mismatch` replaces any earlier `knowledge_meta_masquerade` concept. There is no special-casing for knowledge-asset entity type names.

---

## 2. Payload Field Definitions

### 2.1 Object Type

An object_type draft in business_v1 MUST have these `payload` fields:

| Field | Type | Required | Constraint |
|-------|------|----------|------------|
| `contract_profile` | string | yes | Literal `"business_v1"` |
| `api_name` | string | yes | `^[a-z][a-z0-9_]*$`, max 64 chars, unique within package object_types |
| `display_name` | string | yes | Non-empty after trimming |
| `primary_key` | string | yes | Must match `api_name` of a Property in this Object Type that has `required: true` |

The draft's root `description` field carries the business definition. No `description` in payload.

**primary_key constraint**: The named Property must:
- Belong to the same Object Type (`payload.object_type == this_object.api_name`).
- Have `payload.required == true`.
- Exist in the same package.

Object Types without at least one `required: true` Property cannot declare a valid `primary_key`.

### 2.2 Property

A property draft in business_v1 MUST have these `payload` fields:

| Field | Type | Required | Constraint |
|-------|------|----------|------------|
| `contract_profile` | string | yes | Literal `"business_v1"` |
| `object_type` | string | yes | Must match `api_name` of an Object Type in the same package |
| `api_name` | string | yes | `^[a-z][a-z0-9_]*$`, max 64 chars, unique within (object_type, api_name) |
| `display_name` | string | yes | Non-empty after trimming |
| `value_type` | string | yes | Must be in v1 allowed set (see §3.1) |
| `required` | boolean | yes | `true` or `false` |

The draft's root `description` field carries the business definition.

### 2.3 Link Type

A link_type draft in business_v1 MUST have these `payload` fields:

| Field | Type | Required | Constraint |
|-------|------|----------|------------|
| `contract_profile` | string | yes | Literal `"business_v1"` |
| `api_name` | string | yes | `^[a-z][a-z0-9_]*$`, max 64 chars, unique within package link_types |
| `display_name` | string | yes | Non-empty after trimming |
| `source_object_type` | string | yes | Must match `api_name` of an Object Type in the same package |
| `target_object_type` | string | yes | Must match `api_name` of an Object Type in the same package |
| `cardinality` | string | yes | Must be in v1 allowed set (see §3.2) |

The draft's root `description` field carries the business definition.

Self-referential links (`source_object_type == target_object_type`) are allowed. No link properties (`weight`, `since`, `context`) in v1.

### 2.4 Action Type

An action_type draft in business_v1 MUST have these `payload` fields:

| Field | Type | Required | Constraint |
|-------|------|----------|------------|
| `contract_profile` | string | yes | Literal `"business_v1"` |
| `api_name` | string | yes | `^[a-z][a-z0-9_]*$`, max 64 chars, unique within package action_types |
| `display_name` | string | yes | Non-empty after trimming |
| `target_object_type` | string | yes | Must match `api_name` of an Object Type in the same package |
| `parameters` | list | yes | List of parameter objects (may be empty) |
| `declared_effects` | list[string] | yes | Non-empty list of trimmed, non-empty strings |
| `action_contract` | object | yes | See §2.4.1 |

The draft's root `description` field carries the business definition.

#### 2.4.1 action_contract

| Field | Type | Required | Constraint |
|-------|------|----------|------------|
| `required_role` | string | yes | `admin` \| `owner` \| `member` |
| `confirmation_requirement` | string | yes | `always` \| `conditional` \| `none` |
| `evidence_requirement` | list[string] | yes | Non-empty list of trimmed, non-empty strings |

The Phase 12 package builder already validates `action_contract` (see `ontology_packages.py` lines 130–218). Phase 13 inherits those rules unchanged.

#### 2.4.2 ActionParameter

Each element in `parameters` MUST have:

| Field | Type | Required | Constraint |
|-------|------|----------|------------|
| `name` | string | yes | `^[a-z][a-z0-9_]*$`, max 64 chars |
| `value_type` | string | yes | Must be in v1 allowed set (see §3.1) |
| `required` | boolean | yes | `true` or `false` |

#### 2.4.3 declared_effects

`declared_effects` is a **text-only** declaration. Each element is a human-readable string describing an intended outcome of the action.

**Forbidden content in declared_effects**:
- Handler references (`handler:`, `function:`, `endpoint:`).
- SQL statements or table references.
- Tool names or MCP resource identifiers.
- Function bindings or code references.
- URLs or API paths that imply executable routing.

The validator warns on strings that match these patterns but does not error — `declared_effects` content is advisory at v1.

---

## 3. Controlled Vocabularies

### 3.1 value_type (closed)

| value_type | JSON representation | Description |
|---|---|---|
| `string` | string | UTF-8 text |
| `integer` | number (no fractional part) | Whole number |
| `number` | number (may have fractional part) | Floating-point or decimal |
| `boolean` | boolean | `true` or `false` |
| `date` | string (ISO 8601 date) | `"2026-06-19"` |
| `datetime` | string (ISO 8601 datetime) | `"2026-06-19T10:30:00Z"` |
| `string_list` | array of strings | Ordered list of string values |

**Excluded from v1**: nested objects, structs, union types, generics, expression DSL, custom code types, `MediaReference`, `TimeSeries`, `Geospatial`, enum references.

### 3.2 cardinality (closed)

| cardinality | Meaning |
|---|---|
| `one_to_one` | Each source object links to exactly one target object |
| `one_to_many` | Each source object links to zero or more target objects |
| `many_to_one` | Many source objects may link to the same target object |
| `many_to_many` | Source and target objects can link arbitrarily in both directions |

### 3.3 api_name (constrained format)

All `api_name` values (on Object Types, Properties, Link Types, Action Types, and Action Parameters) MUST match:

```
^[a-z][a-z0-9_]*$
```

- Starts with a lowercase letter.
- Remaining characters: lowercase letters, digits, underscores.
- Maximum length: 64 characters.
- No uppercase, no hyphens, no dots, no leading underscore, no leading digit.

### 3.4 primary_key

`primary_key` on an Object Type MUST reference a Property that:
- Belongs to the same Object Type (`property.payload.object_type == object_type.payload.api_name`).
- Has `property.payload.required == true`.
- Exists in the same package.

A Property with `required: false` cannot serve as `primary_key`.

### 3.5 required_role, confirmation_requirement

Inherited from Phase 12 `action_contract` validation (see `ontology_packages.py`):

| Field | Valid Values |
|-------|-------------|
| `required_role` | `admin`, `owner`, `member` |
| `confirmation_requirement` | `always`, `conditional`, `none` |

`evidence_requirement` must be a non-empty list of trimmed, non-empty strings.

---

## 4. Compiled Manifest Specification

### 4.1 Manifest Structure

The compiled business manifest has three top-level sections:

```json
{
  "manifest": { },
  "provenance": { },
  "object_types": [ ],
  "properties": [ ],
  "link_types": [ ],
  "action_types": [ ]
}
```

#### 4.1.1 manifest

| Field | Type | Description |
|-------|------|-------------|
| `contract_profile` | string | Literal `"business_v1"` |
| `schema_version` | string | Literal `"1.0"` |
| `semantic_hash` | string | `"sha256:"` + 64 hex chars (see §4.2) |

`compiled_at` is deliberately **absent**. Including a timestamp would make the hash non-deterministic across compilations. The manifest is a pure function of the business content.

#### 4.1.2 provenance

| Field | Type | Description |
|-------|------|-------------|
| `source_package_id` | string | UUID of the Phase 12 `OntologyModelPackage` |
| `source_package_version` | integer | Version number of the source package |
| `source_content_hash` | string | SHA-256 of the Phase 12 `contract_json` (canonical form) |

Provenance identifies the immutable audit artifact that this manifest was derived from. It does NOT participate in `semantic_hash`.

#### 4.1.3 Business Definitions

`object_types`, `properties`, `link_types`, and `action_types` are arrays of compiled business entities. Each entry is a cleaned subset of the corresponding Phase 12 contract item, with audit fields removed and business fields normalized.

### 4.2 semantic_hash

**Coverage**: The hash covers ONLY the four business definition arrays — `object_types`, `properties`, `link_types`, `action_types`. It does NOT cover `manifest`, `provenance`, or any top-level metadata.

**Algorithm**:
1. Extract `{"object_types": [...], "properties": [...], "link_types": [...], "action_types": [...]}` as a dict.
2. Serialize with `json.dumps(content_dict, sort_keys=True, ensure_ascii=False, separators=(",", ":"))`.
3. Compute `hashlib.sha256(canonical_bytes).hexdigest()`.
4. Format as `"sha256:" + hex_digest`.

**Stability guarantee**: Same business definitions → same `semantic_hash`, across:
- Different database instances (SQLite vs PostgreSQL).
- Different `content_hash` values on the source package (Phase 12 `content_hash` covers contract_json including audit fields; `semantic_hash` covers only business definitions).
- Different compilations (no timestamp, no compiler identity, no environment variables).

**Difference guarantee**: Different business definitions → different `semantic_hash`. If two packages describe different Object Types, Properties, Links, or Actions, their `semantic_hash` values differ.

### 4.3 Entity Cleanup Rules

Each entity in the compiled manifest is derived from a Phase 12 `contract_json` entry by:

**Removed fields** (audit noise):
- `id` (draft id)
- `reviewed_by`
- `reviewed_at`
- `review_note`
- `source_entity_id`
- `source_relation_id`
- `source_issue_id`
- `source_rag_run_id`
- `evidence_refs`

**Preserved fields** (business content):
- `draft_type` (as `entity_type` in the compiled form: `object_type` / `property` / `link_type` / `action_type`)
- `name`
- `description`
- All fields from `payload` except `contract_profile`, `generator`, `scope`, `generation_key`, `observed_value_types`, `observed_entity_count`, `source_entity_type`, `source_entity_count`.

**Renamed fields**:
- The draft root `name` → compiled `api_name`.
- The draft root `description` → compiled `description`.
- `payload.display_name` → compiled `display_name`.
- For Object Type: `payload.primary_key` → compiled `primary_key`.
- For Property: `payload.object_type` → compiled `object_type`; `payload.value_type` → compiled `value_type`; `payload.required` → compiled `required`.
- For Link Type: `payload.source_object_type` → compiled `source_object_type`; `payload.target_object_type` → compiled `target_object_type`; `payload.cardinality` → compiled `cardinality`.
- For Action Type: `payload.target_object_type` → compiled `target_object_type`; `payload.parameters` → compiled `parameters`; `payload.declared_effects` → compiled `declared_effects`; `action_contract` preserved as-is (already validated by Phase 12 builder).

**`action_contract` in compiled manifest**: The `action_contract` is carried through to the compiled entity unchanged from its validated form in the Phase 12 package. It is part of the business definition and participates in `semantic_hash`.

### 4.4 Sorting Rules

All arrays in the compiled manifest are deterministically sorted:

- `object_types`: by `api_name` ascending.
- `properties`: by `api_name` ascending.
- `link_types`: by `api_name` ascending.
- `action_types`: by `api_name` ascending.

Within an Action's `parameters` array: by `name` ascending.

These sorting rules are applied before `semantic_hash` computation. The compiler never preserves insertion order.

---

## 5. Phase 12 Package Relationship

### 5.1 Derivation, Not Modification

A business_v1 compiled manifest is **derived from** a Phase 12 immutable package. It is a separate artifact:

- The Phase 12 package is **never modified** by the compiler.
- The compiled manifest is **never persisted** (no new database table).
- The manifest carries a `provenance` block pointing back to the source package.

### 5.2 Cross-Database Hash Independence

The Phase 12 `content_hash` covers `contract_json` including audit fields (`reviewed_at`, `reviewed_by`, draft IDs). Different database instances may produce different `content_hash` values for semantically identical business content (e.g., different draft UUIDs after re-creation).

The `semantic_hash` is independent of this. Same business definitions produce the same `semantic_hash` regardless of database, draft IDs, or Phase 12 `content_hash`.

---

## 6. Pilot Model Reference

The Phase 13.5 manufacturing pilot uses exactly 11 hand-crafted drafts. This is a fixed dataset for pipeline verification, not a general modeling framework.

### Object Types (2)

| api_name | display_name | primary_key | description |
|----------|-------------|-------------|-------------|
| `equipment` | Equipment | `equipment_id` | Physical equipment asset on the factory floor |
| `work_order` | Work Order | `work_order_id` | Maintenance work order for equipment repair or inspection |

### Properties (6)

**Equipment** (3 properties):

| api_name | object_type | value_type | required | display_name |
|----------|------------|------------|----------|-------------|
| `equipment_id` | `equipment` | `string` | true | Equipment ID |
| `name` | `equipment` | `string` | true | Equipment Name |
| `status` | `equipment` | `string` | true | Status |

**WorkOrder** (3 properties):

| api_name | object_type | value_type | required | display_name |
|----------|------------|------------|----------|-------------|
| `work_order_id` | `work_order` | `string` | true | Work Order ID |
| `title` | `work_order` | `string` | true | Title |
| `status` | `work_order` | `string` | true | Status |

### Link Types (2)

| api_name | source | target | cardinality | display_name |
|----------|--------|--------|-------------|-------------|
| `equipment_work_orders` | `equipment` | `work_order` | `one_to_many` | Equipment Work Orders |
| `work_order_equipment` | `work_order` | `equipment` | `many_to_one` | Work Order Equipment |

### Action Types (1)

| api_name | display_name | target | parameters |
|----------|-------------|--------|------------|
| `create_work_order` | Create Work Order | `work_order` | `title` (string, required), `equipment_id` (string, required), `priority` (string, required), `description` (string) |

Action `action_contract`: `required_role: admin`, `confirmation_requirement: always`, `evidence_requirement: ["ontology_validation_issue"]`.
Action `declared_effects`: `["Creates a new work order for the specified equipment", "Links the work order to the equipment asset"]`.

---

## 7. Validator Error Codes

The 13.2 business contract validator produces structured issues. All codes defined here are authoritative. The 13.2 implementation uses this list.

### Error codes (block compilation)

| Code | Applies to | Rule |
|------|-----------|------|
| `contract_profile_mismatch` | any | `payload.contract_profile` missing or not `"business_v1"` |
| `missing_api_name` | any | `payload.api_name` missing or empty |
| `invalid_api_name` | any | `payload.api_name` doesn't match `^[a-z][a-z0-9_]*$` or exceeds 64 chars |
| `duplicate_api_name` | OT/Prop/Link/Action | Two entities of same type share `api_name` |
| `missing_display_name` | any | `payload.display_name` missing or empty after trim |
| `missing_primary_key` | OT | `payload.primary_key` missing or empty |
| `primary_key_not_required` | OT | `primary_key` references a Property with `required: false` |
| `primary_key_not_found` | OT | `primary_key` doesn't match any Property `api_name` in this Object Type |
| `primary_key_wrong_object_type` | OT | `primary_key` references a Property belonging to a different Object Type |
| `no_required_property` | OT | Object Type has no Property with `required: true` — cannot declare a valid primary_key |
| `missing_object_type_ref` | Prop | `payload.object_type` missing or empty |
| `object_type_not_found` | Prop/Link/Action | Referenced `object_type` / `source_object_type` / `target_object_type` not found in package |
| `missing_value_type` | Prop/Param | `payload.value_type` missing or empty |
| `invalid_value_type` | Prop/Param | `value_type` not in v1 allowed set |
| `missing_required` | Prop | `payload.required` not a boolean |
| `missing_cardinality` | Link | `payload.cardinality` missing or empty |
| `invalid_cardinality` | Link | `cardinality` not in v1 allowed set |
| `missing_parameters` | Action | `payload.parameters` not a list |
| `invalid_parameter_name` | Action | Parameter `name` doesn't match `^[a-z][a-z0-9_]*$` or exceeds 64 chars |
| `invalid_parameter_value_type` | Action | Parameter `value_type` not in v1 allowed set |
| `missing_declared_effects` | Action | `payload.declared_effects` missing, empty, or contains empty strings |
| `missing_action_contract` | Action | `payload.action_contract` missing or fails Phase 12 validation rules |

### Warning codes (do not block compilation)

| Code | Applies to | Rule |
|------|-----------|------|
| `empty_parameters` | Action | `payload.parameters` is an empty list — action has no inputs |
| `declared_effects_single` | Action | `payload.declared_effects` has only one entry — consider declaring all intended outcomes |
| `declared_effects_binding_hint` | Action | A `declared_effects` string contains text suggesting executable binding (handler:, function:, endpoint:, SQL keywords, URLs, tool:, mcp:, call_/invoke_ patterns) |

### 13.2 Test Constraint

The 13.2 validator test file uses **5–8 parametrized tests total**, not 5–8 per error code. Tests are organized by category (profile/object/property/link/action) with parametrized inputs.

---

## 8. Non-Goals

This specification does NOT define:

- Database tables, migrations, or ORM models.
- API endpoints, routers, or HTTP status codes (those are 13.4 scope).
- Compiler implementation details (13.3 scope).
- Pilot demo script logic (13.5 scope).
- knowledge_meta profile definition (out of Phase 13 scope entirely).
- Multi-profile package selectors or profile negotiation.
- JSON Schema, OpenAPI, GraphQL, or any schema vocabulary generation.
- Frontend, modeling UI, or static assets.
- Object instance storage, Action execution, Functions runtime, OSDK, MCP, Graph RAG, ERP/MES/PLC integration.
