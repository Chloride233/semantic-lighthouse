# R3 Relationship Runtime Enhancement Planning

Status: R3A planning delivered, 2026-06-23.
Lane: R3A Fast (planning/docs only). No code, no API changes, no tests.
Scope: R3 candidate evaluation and direction selection. Implementation deferred to R3B+ slices.

Canonical state remains `docs/project-status.toml`. R2 baseline is `docs/r2-relationship-runtime-query-planning.md`.

## 1. R2 Current Capability Summary

R2 delivered the relationship runtime query foundation (6 slices, 63 tests):

| Capability | Detail |
|------------|--------|
| Contract link_type context | FK/PK property annotations on `link_types[]` in compiled business contract. `_build_contract_context()` returns `link_map` with `source_fk_property`, `target_pk_property`, `cardinality`. FK/PK default resolution from OT `primary_key`. |
| 1-hop traversal | `execute_traversal()` single-hop hash join: resolve link → resolve bindings → validate fields → read CSV/XLSX → build target PK index → stream source, filter, join. |
| 2-hop traversal | Two-hop chaining: resolve all links/bindings/datasets upfront → hop 0 joins raw CSV rows (OT0→OT1) → hop 1 joins intermediate flat dicts (→OT2) via `_join_flat_rows()`. |
| `/runtime/traverse` API | `POST /groups/{gid}/projects/{pid}/runtime/traverse` with Pydantic schemas. Member+ permission. Group/project isolation. ValueError → 422 mapping. |
| Audit/provenance | Migration 0029: 5 nullable columns (`path`, `hop_count`, `link_type_api_names`, `binding_ids`, `dataset_ids`). Fail-closed audit mirroring `execute_query()`. Provenance no-leak verified. |
| Bounded design | Max 2 hops (`_MAX_PATH_LENGTH=3`, Pydantic max_length=3). Root filters only (filter-before-traversal). Flat `{ot}__{field}` output. No SQL/DSL/Graph RAG/MCP/Agent/action writeback. |

### R2 Architecture Constraints (carried forward to R3)

- No SQL, no DSL, no expression strings, no AST.
- No Neo4j, no graph database, no Graph RAG.
- No Agent/MCP tool exposure, no action writeback.
- No cross-package or cross-project traversal.
- Group/project/package isolation enforced per-hop.
- Filter values, storage_path, FK/PK data values never in audit or explain.

## 2. R3 Candidate Directions (priority-ordered)

### 2A. R3B — Nested/Grouped Response Shape

**Priority**: ⭐ Highest (recommended first slice).

**User value**: In one-to-many and one-to-many-to-many traversals, the current flat output produces significant row duplication. Equipment → Maintenance (one-to-many) already produces one row per maintenance record. Equipment → Maintenance → Work Orders (one-to-many-to-many) explodes further. A grouped response shape (`group_by_root: true`) nests child rows under each root row, making the output comprehensible for display and reducing JSON payload size for deeply nested traversals.

```json
// Current flat output (3 rows for EQ1 → 2 maintenance → 3 work orders)
{"rows": [
  {"equipment__name": "Pump-A", "maintenance__type": "preventive", "work_orders__desc": "Replace"},
  {"equipment__name": "Pump-A", "maintenance__type": "preventive", "work_orders__desc": "Inspect"},
  {"equipment__name": "Pump-A", "maintenance__type": "corrective", "work_orders__desc": "Lube"}
]}

// Grouped output (R3B)
{"rows": [{
  "equipment": {"name": "Pump-A"},
  "maintenance": [
    {"type": "preventive", "work_orders": [
      {"desc": "Replace"}, {"desc": "Inspect"}
    ]},
    {"type": "corrective", "work_orders": [
      {"desc": "Lube"}
    ]}
  ]
}]}
```

**Design scope**:
- New `response_shape` parameter in `RuntimeTraverseRequest`: `"flat"` (default, backward-compatible) or `"grouped"`.
- Grouping key: `path[0]` (root OT) only for v1. Nested grouping follows the path structure.
- Each OT's fields become an object (if cardinality is one_to_one/many_to_one) or an array of objects (if one_to_many/many_to_many).
- `group_by_root` implies a tree: root → children → grandchildren, following `explain.hops[].cardinality`.

**Technical risk**: Low. The join already produces all data; grouping is a post-processing transformation. No change to join logic, authorization, or audit.

**API/schema change**: Yes — new `response_shape` field on `RuntimeTraverseRequest`. New `RuntimeTraverseGroupedResponse` model. `TraverseExplain` may gain `response_shape` metadata.

**DB migration**: No.

**Recommended test scope** (~8-12 tests):
- `response_shape="flat"` produces identical output to current (backward compat).
- `response_shape="grouped"` single-hop: correct nesting.
- `response_shape="grouped"` two-hop: correct two-level nesting.
- Empty result → empty groups, not null.
- explain_only still works with both shapes.
- explain includes `response_shape` metadata.
- Router test: invalid response_shape rejected 422.
- Router test: grouped response provenance safety (no paths, no filter values).
- Audit unchanged; verify audit fields still correct with grouped response.

**Non-goals**:
- ❌ Arbitrary nested graph / DAG response (flat or single-root tree only).
- ❌ Client-selectable grouping key beyond path[0].
- ❌ Aggregation within groups (COUNT, SUM — deferred to R3E).
- ❌ Frontend rendering changes.
- ❌ Audit schema changes.

### 2B. R3C — Filter Pushdown on Intermediate/Target OTs

**Priority**: ⭐ High.

**User value**: Currently filters only apply to `path[0]` (root OT). A user querying `equipment → maintenance → work_orders` cannot filter on `maintenance.type = "corrective"` or `work_orders.priority = "high"`. Filter pushdown enables narrowing traversal at any hop, reducing unnecessary joins and matching intuitive query patterns.

**Design scope**:
- Allow `filters` to specify `{ot_api_name: {field: value}}` for ANY OT in the path.
- Hop 0 (root): apply filter before first join (current behavior, unchanged).
- Hop 1+ (intermediate/target): apply filter on the joined intermediate rows before building the next target index or before the next join step.
- AND semantics across filters on the same OT.
- Filters on different OTs are independent (no cross-OT AND/OR).

**Technical risk**: Medium. Filtering on joined flat dicts requires knowing which fields are available at each stage. Type conversion must handle values from already-converted intermediate rows (not raw CSV strings). Error messages must clearly identify which OT the invalid filter belongs to.

**API/schema change**: Yes — `filters` already accepts `{ot: {field: value}}` in the schema. Current implementation only reads root OT. R3C would read all OTs. Backward compatible (omitted OTs mean no filter).

**DB migration**: No.

**Recommended test scope** (~8-12 tests):
- Filter on intermediate OT (hop 1) correctly narrows results.
- Filter on target OT (hop 2) correctly narrows results.
- Multiple filters on different OTs compose correctly (AND within each OT).
- Filter field not in intermediate OT's contract → 422 with correct error code.
- Filter value type mismatch on intermediate OT → 422 with type_conversion.
- explain records filter_field_names_by_ot for all filtered OTs.
- Audit records filter_field_names for all filtered OTs.
- Filter values never leak into explain or audit.

**Non-goals**:
- ❌ Cross-OT filter expressions (e.g., `equipment.name = maintenance.type`).
- ❌ OR semantics across filters.
- ❌ Filter on FK/PK join columns (these are internal; users filter on business fields).

### 2C. R3D — Bidirectional Traversal

**Priority**: Medium.

**User value**: Currently all links are traversed in the declared direction (source → target). A user who wants "all equipment for a given maintenance type" must reverse the path mentally and hope the reverse link_type exists. Bidirectional traversal allows `traverse_direction: "reverse"` or automatic reverse resolution, making the API usable for exploratory queries from any starting point.

**Design scope**:
- Two modes: (a) explicit `traverse_direction` per hop, or (b) automatic reverse link resolution when no forward link exists.
- Reverse link resolution: swap source/target OT, swap FK/PK properties. The source (original target) FK becomes the lookup key; the target (original source) PK becomes the index key.
- Cardinality reverses: one_to_many ↔ many_to_one.

**Technical risk**: Medium-High. FK/PK column resolution must be reversed correctly. The join logic (`source_fk → target_pk` in the current direction) becomes `source_pk → target_fk` in reverse. This changes which columns are indexed and which are looked up. Audit and explain must record the effective direction per hop.

**API/schema change**: Yes — new `traverse_direction` field or per-hop direction array. Explain `hops[]` gains `effective_direction` field.

**DB migration**: No (no new columns needed; audit `link_type_api_names` already identifies the link).

**Recommended test scope** (~10-15 tests):
- Reverse single-hop produces correct results.
- Reverse two-hop produces correct chained results.
- Forward direction still works (backward compat).
- Reverse on cardinality: one_to_many → many_to_one grouping.
- Reverse with no valid FK/PK → 422.
- Explain records effective_direction per hop.
- Audit records correct link_type_api_names (unchanged — same link, reversed).

**Non-goals**:
- ❌ Automatic bidirectional link_type creation in contracts.
- ❌ Symmetric traversal (same result both directions) — data may differ.
- ❌ Multi-direction per hop (only forward or reverse, not both simultaneously).

### 2D. R3E — Aggregation and Sorting

**Priority**: Medium-Low.

**User value**: Users want to answer questions like "how many maintenance records per equipment?" or "top 5 work orders by priority." Aggregation (COUNT, SUM, AVG, MIN, MAX) and sorting (ORDER BY field ASC/DESC) are natural query extensions. However, they significantly complicate the response shape and audit model.

**Design scope**:
- `aggregations`: `[{function: "count"|"sum"|"avg"|"min"|"max", field: "ot__prop", alias: "total"}]`.
- `order_by`: `[{field: "ot__prop", direction: "asc"|"desc"}]`.
- Aggregation runs before grouping (if combined with R3B) or on flat rows.
- Sorting runs after aggregation (or on flat rows if no aggregation).

**Technical risk**: High. Aggregation and sorting are the first steps toward a query DSL. The response shape for aggregations is fundamentally different from row output. Audit must record aggregation functions without values. The risk of accidental SQL creep is real — every added function (COUNT, SUM, AVG) moves closer to a full query language.

**API/schema change**: Yes — new `aggregations` and `order_by` fields on request. New response fields for aggregate values. Explain gains aggregation metadata.

**DB migration**: No (aggregation is in-memory on already-joined rows).

**Recommended test scope** (~12-18 tests):
- COUNT aggregation on root OT.
- SUM/AVG on numeric field.
- Multiple aggregations in one request.
- ORDER BY single field ASC/DESC.
- ORDER BY multiple fields.
- Aggregation + sorting combined.
- Aggregation on grouped response (if R3B delivered first).
- Invalid aggregation function → 422.
- Aggregation on non-numeric field → 422.
- Audit records aggregation functions (not values).

**Non-goals**:
- ❌ GROUP BY arbitrary fields (only root grouping from R3B).
- ❌ HAVING clause.
- ❌ Sub-queries or nested aggregations.
- ❌ Window functions.
- ❌ SQL generation or expression DSL.

### 2E. R3F — FK Indexing and Performance Thresholds

**Priority**: Low (optimization — not needed for current data scale).

**User value**: Current hash-join uses in-memory `dict` indexes (O(n) build, O(1) lookup per FK). For datasets approaching 100K+ rows, memory pressure may become an issue. This slice adds configurable scan limits, disk-backed merge join, or warning thresholds.

**Design scope**:
- Per-dataset scan limit configurable via `settings` (already exists: `dataset_max_scan_rows`).
- Warning in explain when scan truncated: `scan_truncated` (already implemented).
- Optional: sort-merge join for sorted datasets (avoids building full in-memory index).
- Optional: streaming join with bounded memory (chunked target index).

**Technical risk**: Medium. Performance work without measured bottlenecks risks premature optimization. Current datasets are small (manufacturing demo: ~279 rows total, 13 tables). Need real-world scale data before optimizing.

**API/schema change**: No (settings-level changes only).

**DB migration**: No.

**Recommended test scope** (~5-8 tests):
- Scan truncation warning in explain when limit exceeded.
- Large dataset (>10K rows) join completes within time budget.
- Memory usage stays within configured bound.
- No silent data loss on truncation.

**Non-goals**:
- ❌ Database-level indexing (no SQL indexes on CSV files).
- ❌ Query planner or cost-based optimization.
- ❌ Parallel/distributed join execution.
- ❌ Caching layer (datasets re-read on each request; caching is a broader infra concern).

## 3. R3 Candidate Comparison

| Dimension | R3B Grouped | R3C Filters | R3D Bidirectional | R3E Agg/Sort | R3F Perf |
|-----------|-------------|-------------|-------------------|--------------|----------|
| User-facing value | High (readability) | High (query power) | Medium | Medium-Low | Low (current scale) |
| Risk | Low | Medium | Medium-High | High (DSL creep) | Medium |
| API change | Yes | No (schema exists) | Yes | Yes | No |
| DB migration | No | No | No | No | No |
| Backward compat | Full (default flat) | Full | Full | Full (no agg = rows) | Full |
| Joins R2 audit model | No change | No change | explain only | No change | No change |
| Estimated tests | ~10 | ~10 | ~12 | ~15 | ~6 |

## 4. Recommended First Implementation Slice: R3B

**Recommendation**: Start with R3B group_by_root response shape.

**Reasons**:
1. **Highest demo/readability ROI**: Flat row explosion is the most visible UX gap in the current R2 output. A grouped response immediately makes traversal results comprehensible in a demo or product UI.
2. **Lowest technical risk**: Grouping is a post-processing transformation on already-joined rows. Zero change to join logic, FK/PK resolution, authorization, or audit persistence.
3. **No migration**: Pure response-serialization change. No DB schema impact.
4. **Forward-compatible**: Grouped output is a natural foundation for R3E (aggregation within groups) and R3C (filter on intermediate OTs within groups).
5. **Backward-compatible**: Default remains `response_shape="flat"`. Existing clients, tests, and smoke scripts are unaffected.
6. **Proves R3 discipline**: If we can add grouping without SQL/DSL/Graph RAG creep, it validates the R3 boundary approach for subsequent slices.

**Sequencing after R3B**:
- R3C (filter pushdown) pairs naturally with grouped output.
- R3E (aggregation) benefits from grouped foundation.
- R3D (bidirectional) is independent; can be interleaved.
- R3F (performance) waits for scale evidence.

## 5. R3B Design Boundaries

### Request Extension

```python
class RuntimeTraverseRequest(BaseModel):
    # ... existing fields ...
    response_shape: str = Field(default="flat", pattern="^(flat|grouped)$")
    # "flat": current behavior, {ot}__{field} prefixed flat rows
    # "grouped": nested tree following path structure
```

### Response Shape (grouped)

Single-hop `["equipment", "maintenance"]` with `response_shape="grouped"`:
```json
{
  "rows": [
    {
      "equipment": {"name": "Pump-A", "status": "active"},
      "maintenance": [
        {"type": "preventive", "hours": 2.5},
        {"type": "corrective", "hours": 8.0}
      ]
    }
  ],
  "row_count": 1,
  "explain": { "...", "response_shape": "grouped" }
}
```

Two-hop `["equipment", "maintenance", "work_orders"]`:
```json
{
  "rows": [
    {
      "equipment": {"name": "Pump-A"},
      "maintenance": [
        {
          "type": "preventive",
          "work_orders": [
            {"desc": "Replace bearing"},
            {"desc": "Inspect seal"}
          ]
        },
        {
          "type": "corrective",
          "work_orders": []
        }
      ]
    }
  ]
}
```

### Rules

1. **Default flat**: `response_shape` omitted or `"flat"` → current behavior (backward compat).
2. **Grouping key**: `path[0]` only. Deeper grouping follows cardinality from `explain.hops[].cardinality`.
3. **Cardinality-driven nesting**: `one_to_one` / `many_to_one` → single object. `one_to_many` / `many_to_many` → array of objects.
4. **Empty children**: `[]` (empty array), never `null`.
5. **Explain enrichment**: `response_shape` field in explain. No other explain changes.
6. **Audit unchanged**: `field_names`, `filter_field_names`, `row_count` reflect the logical row count (root-level groups), not the flat row count.
7. **type_errors unchanged**: Per-field type errors still reported at the flat level. If a row has type errors, the group is excluded (same as current — type errors → no output for that row).
8. **limit/offset**: Applied to root-level groups, not flat rows.

### Explicit Non-Goals for R3B

- ❌ Arbitrary nested graph / DAG response.
- ❌ Client-selectable grouping key beyond path[0].
- ❌ Aggregation within groups (COUNT, SUM — R3E).
- ❌ Frontend rendering changes.
- ❌ Audit DB schema changes.
- ❌ SQL/DSL/expression generation.
- ❌ Graph RAG or Neo4j.
- ❌ Agent/MCP/action writeback.

## 6. R3 Implementation Sequencing

```
R3A (this doc) → R3B (grouped response) → R3C (filter pushdown) → R3D (bidirectional) → R3E (aggregation) → R3F (performance)
```

Each slice is independently valuable and testable. R3C and R3B can be developed in either order, but B→C is recommended because grouped output makes filter pushdown semantics clearer. R3D is independent and can be interleaved at any point. R3E and R3F are lower priority and should wait for measured demand.

## 7. Risk: R3 Must Not Become SQL/DSL Creep

The primary R3 risk is incremental feature addition that accumulates into an ad-hoc query language. Each slice (filter pushdown → aggregation → sorting) moves closer to SQL territory. Guardrails:

1. **No expression strings**: All parameters are structured JSON (field names, values, function names). No `"filter": "equipment.status = 'active' AND maintenance.type = 'preventive'"`.
2. **No cross-OT expressions**: Filters on OT A cannot reference fields from OT B. Each OT's filters are independent.
3. **No sub-queries or nesting**: `aggregations` cannot contain sub-aggregations. `order_by` cannot reference aggregate aliases dynamically.
4. **Bounded function set**: Aggregation functions are a fixed enum (`count`, `sum`, `avg`, `min`, `max`). No custom functions, no UDFs.
5. **Explain, don't optimize**: The explain block exposes what happened, not an execution plan. No query planner, no cost model.
6. **Review gate**: Before any R3 slice that adds parameterized computation (R3C, R3E), review against this checklist and confirm no SQL/DSL boundary creep.

## 8. Next Steps

1. **R3B implementation**: Add `response_shape` parameter, `_group_flat_rows()` post-processing function, grouped response model, and tests. Lane: Standard. ✅ Delivered (2026-06-23).
2. **R3C (after R3B)**: Filter pushdown on intermediate/target OTs. Lane: Safety (changes filter semantics). ✅ Delivered (2026-06-23).
3. **R3D**: Bidirectional traversal. Lane: Standard. ✅ Delivered (2026-06-24).
4. **R3E design decision**: See `docs/r3e-aggregation-sorting-design.md` (2026-06-24). Recommendation: R3E1 sorting only, skip aggregation indefinitely.
5. **R3F**: FK indexing. Deferred until R3E1 is delivered or skipped.
