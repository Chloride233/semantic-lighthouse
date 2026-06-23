# R2 Relationship Runtime Query Planning

Status: R2A planning + R2B contract context + R2C traversal core delivered, 2026-06-23.
Lane: R2A Safety (design); R2B+R2C Standard (compiler/validator/context + traversal service, no DB/API).
Scope: R2A design + R2B compiler/validator/context + R2C single-hop hash join traversal. No router, no endpoint, no migration.

Canonical state remains `docs/project-status.toml`.

## Purpose

R2 takes the project from "single object_type query" to "limited package-declared
relationship path traversal," closing the biggest gap in the ontology four-chain
route (object/permission chains strong, relationship chain needs runtime support).

R2 is the direct follow-up to R1 (refactor complete) and the implementation target
identified in `docs/palantir-ontology-four-chain-gap-analysis.md`.

## 1. Where Is Relationship Information Currently?

There are **three separate stores**, none of which the runtime query path consumes:

### 1A. Business Contract `link_types` (compiled, canonical, NOT consumed at runtime)

- **Source**: `OntologyModelPackage.contract_json` → `link_types[]`
- **Compiled by**: `business_contract_compiler.py` → compiled output `link_types[]`
- **Each link_type**: `entity_type`, `api_name`, `display_name`, `description`, `source_object_type`, `target_object_type`, `cardinality`
- **Validated by**: `business_contract_validator.py` `_validate_link_type()` — checks source/target object_types exist in package, cardinality ∈ {one_to_one, one_to_many, many_to_one, many_to_many}
- **Compiled output fields**: `LINK_FIELDS = frozenset({"entity_type", "api_name", "display_name", "description", "source_object_type", "target_object_type", "cardinality"})`
- **Critical gap**: `_build_contract_context()` in `runtime_contract.py` extracts `ot_map`, `prop_map`, `fields_by_ot` from the compiled contract but **does NOT extract `link_types`**. The link_type information is compiled and validated but never reaches the runtime query path.

### 1B. Mapping Contract `relationship_mappings` (offline artifact, NOT in DB)

- **Source**: `scripts/generate_mapping_contract.py` → `mapping_contract.json`
- **Derived from**: `manifest.json` foreign_keys + `TABLE_SCHEMAS`
- **Each relationship**: `relationship_name`, `source_table`/`source_columns` (FK), `target_table`/`target_columns` (PK), `cardinality`, `core_pilot`, `evidence_source`
- **Status**: Offline JSON artifact only. No database table, no runtime binding, no API endpoint.
- **15 relationships, 7 core_pilot** in the manufacturing data pack.
- **Gap**: Maps table columns (e.g. `equipment.work_center_id`), NOT Ontology property api_names (e.g. `equipment_csv_work_center_id`). Cannot be directly consumed by runtime query which works with property api_names via `binding.property_mappings`.

### 1C. Ontology Relations (Phase 9, document-scan level)

- **Source**: `ont_relations` DB table, populated by ontology scan from documents
- **Fields**: `relation_type`, `source_entity_id`, `target_entity_id`, `evidence_document_id`
- **Status**: Knowledge-graph-level relations from document analysis. Not binding-level FK mappings. Not directly usable for dataset-to-dataset traversal.

### Decision

For R2 v1, the **single source of truth for relationship traversal authorization** must be the
**compiled business contract's `link_types` array**, because:

1. It is already compiled, validated, and versioned with the package (via `semantic_hash`).
2. It references ontology Object Type api_names (not raw table names), matching the runtime's vocabulary.
3. It is the same authoritative source used for object_type and property validation.

However, link_types currently lack **FK column resolution** — they declare `source_object_type → target_object_type` but do not specify **which property in source** holds the FK value or **which property in target** is the PK. This must be addressed in R2B (see §9 — Prerequisites for Implementation).

## 2. Is Existing Runtime Binding Sufficient for Relationship Traversal?

**No.** The current runtime architecture is single-object-type only:

| Capability | Current State | Gap |
|---|---|---|
| Binding model | `OntologyDatasetBinding` maps one object_type → one dataset | No concept of FK columns, join keys, or related object types |
| Contract context | `_build_contract_context()` returns `ot_map`, `prop_map`, `fields_by_ot` | Does NOT extract `link_types` |
| Query execution | `execute_query()` streams a single CSV/XLSX file | Single-file only. No cross-dataset reads. |
| FK resolution | Not present anywhere in runtime path | No mechanism to find which column in dataset A matches which column in dataset B |
| Property mappings | `binding.property_mappings`: `{prop_api_name: column_name}` | Maps properties to columns within ONE dataset. Cannot express "this property is a FK to another object_type's PK" |

### What R2 Must Add

1. **Contract context**: `_build_contract_context()` must also extract `link_types` into a `link_map` keyed by `api_name`, with `source_object_type`, `target_object_type`, `source_fk_property`, `target_pk_property`, `cardinality`.
2. **FK column resolution**: At traversal time, resolve `source_fk_property` → source binding's `property_mappings` → source column name; same for `target_pk_property` → target binding's `property_mappings` → target column name.
3. **Multi-binding resolution**: Each hop needs TWO bindings (source and target), both validated for group_id/project_id/package_id/status="active".
4. **Hash-join logic**: Stream source dataset, for each matching row, read target dataset and match FK value = PK value (in-memory index for small datasets; scan for v1).

## 3. R2 v1 Minimum Query Shape

### Example Target Queries

```text
# One hop: equipment → equipment_maintenance
equipment.equipment_id = equipment_maintenance.equipment_id (FK)

# Two hops: equipment → equipment_maintenance → work_orders  
# (no direct FK between equipment_maintenance and work_orders in current schema,
# but the pattern generalizes to any declared link_type chain)
```

### Declarative Path Model

R2 v1 introduces a **declarative path** — an ordered list of object_type api_names.
The system resolves which `link_type` connects each adjacent pair.

**Request shape** (new endpoint, see §7):

```json
{
  "path": ["equipment", "equipment_maintenance"],
  "fields": {
    "equipment": ["equipment_name", "status"],
    "equipment_maintenance": ["maintenance_type", "scheduled_date", "status"]
  },
  "filters": {
    "equipment": {"status": "active"}
  },
  "max_path_length": 2,
  "limit": 20,
  "offset": 0,
  "explain_only": false
}
```

### Response Shape — Flat Joined (v1)

Each result row is a **flat dictionary** with field names prefixed by `{object_type}__`:

```json
{
  "rows": [
    {
      "equipment__equipment_name": "CNC Lathe-01",
      "equipment__status": "active",
      "equipment_maintenance__maintenance_type": "preventive",
      "equipment_maintenance__scheduled_date": "2025-06-15",
      "equipment_maintenance__status": "completed"
    },
    {
      "equipment__equipment_name": "CNC Lathe-01",
      "equipment__status": "active",
      "equipment_maintenance__maintenance_type": "corrective",
      "equipment_maintenance__scheduled_date": "2025-07-01",
      "equipment_maintenance__status": "scheduled"
    }
  ],
  "row_count": 2,
  "explain": {
    "package_id": "uuid",
    "package_version": 3,
    "package_semantic_hash": "sha256:...",
    "path": ["equipment", "equipment_maintenance"],
    "hops": [
      {
        "hop_index": 0,
        "link_type_api_name": "equipment_to_equipment_maintenance",
        "source_object_type": "equipment",
        "target_object_type": "equipment_maintenance",
        "cardinality": "one_to_many",
        "source_binding_id": "uuid",
        "target_binding_id": "uuid",
        "source_dataset_id": "uuid",
        "target_dataset_id": "uuid",
        "source_fk_property": "equipment_id",
        "target_pk_property": "equipment_id"
      }
    ],
    "selected_fields_by_ot": {
      "equipment": ["equipment_name", "status"],
      "equipment_maintenance": ["maintenance_type", "scheduled_date", "status"]
    },
    "filter_field_names_by_ot": {
      "equipment": ["status"]
    },
    "limit": 20,
    "offset": 0,
    "scanned_rows": {"equipment": 50, "equipment_maintenance": 200},
    "matched_before_paging": 2
  }
}
```

### Design Rationale for Flat Response

- **Simplest to implement** for v1: no recursive nesting, no tree construction.
- **Compatible with existing response model**: still `rows: list[dict]`, `row_count`, `explain`.
- **Prefix convention** avoids field name collisions across object types.
- **One-to-many relationships** produce multiple rows (one per related target row), which is natural for tabular display.
- Future versions (R3+) can add nested/grouped responses without breaking the flat format.

## 4. Scope Restrictions

### 4A. Only Package-Declared Link Types

- Traversal is **authorized by the compiled business contract's `link_types` array**.
- Each hop must match exactly one `link_type` where `source_object_type` = path[i] and `target_object_type` = path[i+1].
- If zero or multiple link_types match, the request is rejected with `ambiguous_link_type` or `no_link_type`.
- Link types from stale packages are never used — the latest package is always resolved per request.

### 4B. Limited Path Length

- **Default max**: 2 hops (configurable via `settings.runtime_max_traversal_hops`, hardcoded to 2 for v1).
- Path length = `len(path) - 1` (number of hops).
- Enforcement: Pydantic `max_length` on the `path` list, plus server-side clamp.

### 4C. Whitelist Fields Only

- Fields per object_type must be in the compiled contract's `fields_by_ot[ot]` AND the binding's `property_mappings`.
- Same validation as current single-object query, applied independently per object_type in the path.
- If `fields` is omitted for an object_type, all bound contract fields are returned for that OT.

### 4D. Explicit Non-Goals

- ❌ No arbitrary JOIN (no SQL, no DSL, no expression strings).
- ❌ No Graph RAG.
- ❌ No Neo4j or graph database.
- ❌ No Agent/MCP tool exposure.
- ❌ No action writeback.
- ❌ No cross-package traversal (all hops must use the same package).
- ❌ No cross-project or cross-group traversal.
- ❌ No recursive/transitive closure.
- ❌ No `*` wildcard for fields.

## 5. Permissions and Isolation

### 5A. Role Requirements

| Operation | Minimum Role |
|---|---|
| `POST /runtime/traverse` | member+ (same as existing `POST /runtime/query`) |

Owner/admin do not need additional capabilities for traversal — the permissions are bounded by the data they can already query individually.

### 5B. Per-Hop Isolation

Every hop in the traversal MUST independently verify:

1. **Source binding**: `group_id == group_id`, `project_id == project_id`, `package_id == latest_package.id`, `status == "active"`.
2. **Target binding**: same checks.
3. **Source dataset**: `group_id == group_id`, `project_id == project_id`, `status == "ready"`.
4. **Target dataset**: same checks.
5. **Both bindings belong to the same package**: `source_binding.package_id == target_binding.package_id`.

Failure at any hop produces a `422` with stable error code (e.g. `no_binding_for_hop`, `cross_project_traversal_rejected`).

### 5C. Package Scope

All hops must resolve against **the same latest package**. The package is resolved once at the start of traversal and reused for all hops. This prevents:
- Mixing bindings from different package versions.
- Traversal across packages with different semantic hashes.

## 6. Audit and Provenance

### 6A. Audit Fields Added

`OntologyRuntimeAudit` (operation = `"traverse"`) records the following **additional** fields beyond the existing `query` audit shape:

| Field | Type | Description |
|---|---|---|
| `path` | `list[str]` | Ordered object_type api_names traversed |
| `hop_count` | `int` | Number of hops (= len(path) - 1) |
| `link_type_api_names` | `list[str]` | Resolved link_type api_name per hop |
| `binding_ids` | `list[str]` | Binding IDs per object_type in path |
| `dataset_ids` | `list[str]` | Dataset IDs per object_type in path |

Existing audit fields reused:
- `field_names`: flat list of all `{ot}__{prop}` fields returned.
- `filter_field_names`: flat list of all `{ot}__{prop}` filter fields.
- `limit_val`, `offset_val`, `outcome`, `row_count`, `error_code`, `error_summary`.

### 6B. Explain Fields Added

The `explain` block in the response includes:

| Field | Description |
|---|---|
| `path` | Ordered object_type api_names |
| `hops[]` | Per-hop: `hop_index`, `link_type_api_name`, `source_object_type`, `target_object_type`, `cardinality`, `source_binding_id`, `target_binding_id`, `source_dataset_id`, `target_dataset_id`, `source_fk_property`, `target_pk_property` |
| `selected_fields_by_ot` | `{object_type: [field_names]}` — replaces flat `selected_fields` |
| `filter_field_names_by_ot` | `{object_type: [filter_field_names]}` — replaces flat `filter_field_names` |
| `scanned_rows` | `{object_type: count}` — per object_type scan counts |
| `matched_before_paging` | int — total matched rows before offset/limit |

### 6C. Prohibited in Audit and Explain

Same prohibitions as current single-object query, plus:

- ❌ FK/PK **values** used for join (these are data, not metadata).
- ❌ Intermediate row data from any hop.
- ❌ Storage paths for any dataset.
- ❌ Filter values (only filter field names, same as current).
- ❌ Raw data, PII, secrets, stack traces.

### 6D. Audit Fail-Closed

Same as current: if audit write fails, the traversal result MUST NOT be returned to the caller. The transaction is rolled back.

## 7. API Design

### Recommendation: New Endpoint

**Rationale**: Clean separation from single-object query. Different request/response shape. Different error codes. Easier independent iteration and deprecation later.

### New Endpoint

```
POST /groups/{group_id}/projects/{project_id}/runtime/traverse
```

### Request Schema (`RuntimeTraverseRequest`)

```python
class RuntimeTraverseRequest(BaseModel):
    path: list[str] = Field(..., min_length=2, max_length=3)
    # min_length=2 → at least [source, target] (one hop)
    # max_length=3 → at most [a, b, c] (two hops)

    fields: dict[str, list[str]] | None = Field(default=None)
    # {object_type_api_name: [field_names]}
    # If omitted for an OT, all bound contract fields returned.

    filters: dict[str, dict[str, str | int | float | bool | None]] | None = Field(default=None)
    # {object_type_api_name: {field_name: value}}
    # Only root object_type filters in v1 (filter-before-traversal semantics).

    max_path_length: int = Field(default=2, ge=1, le=2)
    # Server-side safety clamp.

    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0, le=10000)
    explain_only: bool = Field(default=False)
```

### Response Schema (`RuntimeTraverseResponse`)

```python
class HopExplain(BaseModel):
    hop_index: int
    link_type_api_name: str
    source_object_type: str
    target_object_type: str
    cardinality: str
    source_binding_id: str
    target_binding_id: str
    source_dataset_id: str
    target_dataset_id: str
    source_fk_property: str
    target_pk_property: str

class TraverseExplain(BaseModel):
    package_id: str
    package_version: int
    package_semantic_hash: str
    path: list[str]
    hops: list[HopExplain]
    selected_fields_by_ot: dict[str, list[str]]
    filter_field_names_by_ot: dict[str, list[str]]
    limit: int
    offset: int
    scanned_rows: dict[str, int] | None = None
    scan_limit: int | None = None
    scan_truncated: dict[str, bool] | None = None
    matched_before_paging: int | None = None

class RuntimeTraverseResponse(BaseModel):
    rows: list[dict]
    row_count: int | None
    explain: TraverseExplain
    type_errors: list[dict] | None = None
```

### Decision: Do NOT Extend Existing `/runtime/query`

Extending the existing endpoint with an optional `path` field would:
- Complicate the single-object code path with conditional branching.
- Make error codes ambiguous ("was this a query error or a traversal error?").
- Risk breaking existing clients that depend on the current response shape.

### Error Codes

| HTTP Status | Error Code | Condition |
|---|---|---|
| 422 | `no_link_type` | No link_type connects two adjacent object_types in path |
| 422 | `ambiguous_link_type` | Multiple link_types connect the same pair (should not happen with well-formed contracts) |
| 422 | `no_binding_for_hop` | No active binding for an object_type in the path |
| 422 | `cross_package_traversal` | Bindings for different hops belong to different packages |
| 422 | `max_path_length_exceeded` | Path length > configured max |
| 422 | `invalid_fields` | Field not in contract or binding for a given object_type |
| 422 | `invalid_filter` | Filter field not in contract or binding |
| 422 | `fk_property_not_in_contract` | link_type's source_fk_property or target_pk_property not in compiled contract |
| 422 | `no_package` | No project package found |
| 422 | `dataset_not_ready` | A dataset in the path is not ready |
| 422 | `type_conversion` | Type conversion error in any hop |
| 403 | (standard) | Not a group member |
| 404 | (standard) | Project not found |
| 409 | (standard) | Project archived |

All error codes are sanitized through `_sanitized_code()` — internal error types are never exposed.

## 8. R2 Implementation Plan

### Sequencing

R2 is implemented as slices to de-risk each layer independently:

- **R2A** (this document): Planning and design. No code.
- **R2B**: Contract context extension. Add `link_types` to `_build_contract_context()` return dict. Add `link_map` keyed by `api_name`. This requires NO migration — it's a pure runtime data structure change. Unit tests for context shape. ✅ **Delivered 2026-06-23** — `LINK_FIELDS` extended, `_validate_link_type` validates FK/PK properties, `_build_contract_context` returns `link_types` and `link_map` with FK/PK resolution and OT primary_key default. 149/149 tests pass.
- **R2C**: Traversal core in `services/runtime_traverse.py`. New `execute_traversal()` function. Single-hop first. Hash-join over CSV datasets using FK/PK resolution from bindings. Unit tests with mock datasets. ✅ **Delivered 2026-06-23** — `execute_traversal()` with single-hop hash join, fields per OT, root filters, limit/offset, explain_only, flat `{ot}__{field}` prefix output. 25 unit tests. 174/174 tests pass.
- **R2D**: Router and API. New `POST /runtime/traverse` endpoint. Request/response validation. Permission wiring. Integration tests. ✅ **Delivered 2026-06-23** — New endpoint in `routers/runtime.py`, `RuntimeTraverseRequest`/`RuntimeTraverseResponse` schemas in `schemas.py`, non-root filters rejected with 422, 17 integration tests, 42 total traverse tests pass.
- **R2E**: Audit and provenance. Extend `OntologyRuntimeAudit` to support `traverse` operation. Add `path`, `hop_count`, `link_type_api_names`, `binding_ids`, `dataset_ids` fields. Audit tests for success/failure/fail-closed/provenance-no-leak. ✅ **Delivered 2026-06-23** — Alembic migration 0029 adds 5 nullable columns. Model, `_record_audit`, and `execute_traversal` updated with fail-closed audit. 10 audit tests pass.
- **R2F**: Multi-hop (second hop). Generalize single-hop to N-hop. Path-length enforcement. Cross-hop binding validation. Multi-hop tests. ✅ **Delivered 2026-06-23** — `execute_traversal` supports path length 2–3 (1–2 hops). Two-hop chains resolve all links/bindings/datasets upfront, hash-join via `_join_flat_rows`. `RuntimeTraverseRequest.path` max_length=3. 11 two-hop tests, 63 total traverse tests pass. No DB migration.

### Migration Impact

- **R2B–R2D**: No database migrations required if audit fields are added as nullable columns.
- **R2E**: One Alembic migration to add new columns to `ontology_runtime_audit` (all nullable, no backfill required).
- **No new tables** needed — bindings, datasets, packages are all reused.

### Dependencies

- R1 refactor (complete) provides clean module boundaries: `runtime_query`, `runtime_contract`, `runtime_dataset_io`, `runtime_audit`.
- `runtime_traverse` imports from all four, plus adds its own traversal logic.
- No circular import risk: `runtime_traverse` is a consumer, not a dependency of existing modules.

## 9. Prerequisites for R2B — What Must Be Resolved Before Code

### 9A. FK Property Annotation on link_type

The compiled business contract's `link_type` entity currently has NO FK/PK property information:

```json
// Current link_type (insufficient for traversal)
{
  "entity_type": "link_type",
  "api_name": "equipment_to_equipment_maintenance",
  "source_object_type": "equipment",
  "target_object_type": "equipment_maintenance",
  "cardinality": "one_to_many"
}
```

For traversal, we need:

```json
// Extended link_type (R2B proposal)
{
  "entity_type": "link_type",
  "api_name": "equipment_to_equipment_maintenance",
  "source_object_type": "equipment",
  "target_object_type": "equipment_maintenance",
  "cardinality": "one_to_many",
  "source_fk_property": "equipment_id",
  "target_pk_property": "equipment_id"
}
```

Where:
- `source_fk_property`: the property api_name in the source object_type that holds the FK value.
- `target_pk_property`: the property api_name in the target object_type that is the PK (defaults to target OT's `primary_key` if omitted).

**Resolution options for R2B**:

1. **Add to link_type entity in contract_json**: Extend `LINK_FIELDS` in compiler, add validation in `_validate_link_type()`. Requires ontology draft/modeling support for these fields (possibly a Phase 20 task).
2. **Derive from mapping_contract.json**: Load mapping_contract.json at runtime (or bake into package). Map table columns → property api_names via binding.property_mappings reverse lookup. More complex but avoids schema change.
3. **Convention-based**: Infer FK property by name convention (e.g. if a property's api_name matches another OT's primary_key api_name). Fragile; not recommended.

**R2A recommendation**: Option 1 (extend link_type entity). This keeps the business contract as the single source of truth and avoids runtime dependency on offline artifacts. The ontology draft UI would need to expose FK/PK property selectors, but that is a Phase 20 concern — for R2B, the extension is a schema+compiler change only.

### 9B. link_type Contract Validation Extension

`_validate_link_type()` in `business_contract_validator.py` must additionally validate:
- `source_fk_property` exists as a property of `source_object_type` in the package.
- `target_pk_property` exists as a property of `target_object_type` in the package (or defaults to OT's primary_key).
- `source_fk_property`'s value_type matches `target_pk_property`'s value_type (both must be comparable).

### 9C. Binding Completeness Gate

R2 traversal requires that **every object_type in the path has an active binding**. Current `generate_bindings` creates bindings for dataset-backed OTs only. If an OT exists in the contract but has no dataset (e.g. a "virtual" or "computed" OT), traversal through it fails with `no_binding_for_hop`.

This is acceptable for v1 — only dataset-backed OTs are traversable.

## 10. Test Plan

### 10A. Cross-Group Isolation

| Test | Expected |
|---|---|
| User in group A traverses path using group A's package/bindings | 200 |
| User in group A traverses path with group B's project_id in URL | 404 (project not found in group A) |
| User in group B traverses path with group A's project_id in URL | 403 (not a member of group A) |
| Two bindings in path belong to different groups | 422 `cross_package_traversal` |

### 10B. Cross-Project Isolation

| Test | Expected |
|---|---|
| Path references object_types only in project P1 | 200 |
| Path includes object_type that has binding only in project P2 | 422 `no_binding_for_hop` |
| Two bindings in path belong to different projects | 422 `cross_package_traversal` |

### 10C. Undeclared Relationship Rejection

| Test | Expected |
|---|---|
| Path `["equipment", "nonexistent_ot"]` — target OT not in contract | 422 `no_link_type` |
| Path `["equipment", "work_orders"]` — no link_type connects them | 422 `no_link_type` |
| Path with valid link_type but link_type has no FK property annotation | 422 `fk_property_not_in_contract` |

### 10D. Missing Binding Rejection

| Test | Expected |
|---|---|
| Valid link_type but source OT has no active binding | 422 `no_binding_for_hop` |
| Valid link_type but target OT has no active binding | 422 `no_binding_for_hop` |
| Binding exists but is `stale` (status != "active") | 422 `no_binding_for_hop` |

### 10E. Path Length Limit

| Test | Expected |
|---|---|
| Path length 2 (one hop) | 200 |
| Path length 3 (two hops) with max_path_length=2 | 200 |
| Path length 4 (three hops) with max_path_length=2 | 422 `max_path_length_exceeded` |
| Path length 1 (single OT — should use /runtime/query instead) | 422 (Pydantic min_length=2) |

### 10F. Provenance No-Leak

| Test | Expected |
|---|---|
| explain contains no FK/PK values | Assert `explain` string contains no data values |
| audit contains no FK/PK values | Assert audit JSON contains no data values |
| explain contains no storage_path | Assert `storage_path` not in explain |
| audit contains no raw data, PII, secrets | Same assertions as existing `test_audit_never_contains_filter_values` |

### 10G. Audit Success/Failure

| Test | Expected |
|---|---|
| Successful traversal writes audit with outcome="success" | audit row_count = result row_count |
| Failed traversal (no link_type) writes audit with outcome="failure" | audit error_code = "no_link_type" |
| Empty traversal (0 matching rows) writes audit with outcome="empty" | audit row_count = 0 |
| Audit write failure → response not returned to caller | 500 or RuntimeError, no data in response |
| Traversal audit has path, hop_count, link_type_api_names, binding_ids, dataset_ids | All fields present and correct |

### 10H. Filter-Before-Traversal Semantics

| Test | Expected |
|---|---|
| Filter on root OT reduces rows before traversal | Only filtered root rows participate in join |
| No filter on non-root OT | Filters on `path[1+]` rejected with 422 |
| Filter field not in contract/binding | 422 `invalid_filter` |
| Multiple filters on root OT | All applied before traversal (AND semantics) |

### 10I. Additional Edge Cases

| Test | Expected |
|---|---|
| explain_only=true | No rows returned, explain block complete |
| limit/offset applied after traversal | Correct paging over flat joined rows |
| Empty dataset (header only) | 422 `dataset_not_ready` or empty result |
| XLSX source and CSV target | Works correctly (format-agnostic after binding) |
| Stale package (newer package exists with different bindings) | Latest package used, stale package ignored |
| Type conversion error in any hop | 422 with `type_errors` in response |

## 11. Decisions Not Made (Deferred)

These are intentionally deferred to later phases:

1. **Nested/grouped response shape**: Flat joined for v1. R3+ may add `group_by_root` option.
2. **Bidirectional traversal**: v1 only supports FK direction (source → target). Reverse traversal (target → source via back-reference) deferred.
3. **Filter on non-root object_types**: v1 only filters on root. Multi-hop filter pushdown deferred.
4. **Aggregation**: No COUNT, SUM, AVG, etc. Pure row retrieval.
5. **Sorting**: No ORDER BY. Deterministic streaming order from datasets.
6. **FK indexing**: v1 uses in-memory dict index for target dataset (O(n) build, O(1) lookup). Adequate for ≤ 100K rows.
7. **Streaming joins**: If both datasets are large, v1 may exceed memory. Deferred to R3 with disk-backed merge join.
8. **R2 impact on activation smoke**: Activation smoke currently runs single-object `execute_query`. R2 traversal is a separate operation; activation does NOT need to smoke-test traversals in v1.

## 12. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| FK property not annotated on link_types | High | Block R2C | Resolve in R2B via compiler extension |
| One-to-many produces excessive rows | Medium | Response size | Limit + offset clamp; scan_limit per dataset |
| Cross-dataset FK values don't match (data quality) | Medium | Empty results | Document as expected behavior; explain shows scanned vs matched |
| Memory pressure from hash-join index | Low (v1 datasets are small) | OOM on very large datasets | scan_limit clamp; document max dataset size for traversal |
| Audit table column growth | Low | Migration complexity | All new columns nullable; no backfill |
| Concurrent binding generation during traversal | Low | Stale binding used | Bindings are resolved at request start; no long-lived cursor |

## 13. Next Steps

1. **R2B — Contract Context Extension**: Add `link_types` to `_build_contract_context()`. Extend `LINK_FIELDS` to include `source_fk_property` and `target_pk_property`. Update `_validate_link_type()` for FK/PK property validation. This is a pure schema+compiler change, no runtime traversal yet.
2. **Phase 20 (future)**: Expose FK/PK property selectors in ontology draft UI so users can annotate link_types when building contracts.

## Appendix: Comparison with Current R1 State

| Dimension | R1 (Current) | R2 v1 (This Design) |
|---|---|---|
| Query target | Single object_type | Path of 2-3 object_types |
| Data source | One dataset file | N dataset files (one per OT in path) |
| Binding resolution | One binding | N bindings, all validated |
| Contract usage | ot_map, prop_map, fields_by_ot | + link_map with FK/PK resolution |
| Response shape | `rows: [{field: value}]` | `rows: [{"ot__field": value}]` |
| Error codes | ~10 stable codes | ~10 new traversal-specific codes |
| Audit fields | field_names, filter_field_names | + path, hop_count, link_type_api_names, binding_ids, dataset_ids |
| Max rows per response | 100 | 100 |
| Max data scanned | dataset_max_scan_rows (one file) | dataset_max_scan_rows × N files |
| Permissions | member+ | member+ (unchanged) |
| Activation smoke | Full query smoke | Not affected (traversal is separate) |
