# R3E Aggregation/Sorting — Design-Only Decision

Status: design document, 2026-06-24. No code, no runtime changes, no tests, no commit.
Lane: Fast (design only).

Canonical state: `docs/project-status.toml`. R3D baseline: bidirectional traversal delivered, 101 tests.

---

## 1. Summary

This document answers the three design questions from the R3E gate and provides
a recommendation for the next implementation decision.

### 1.1 Decision Questions

| Question | Answer |
|----------|--------|
| Is aggregation worth doing? | **Not now.** The grouped response (R3B) already provides structural aggregation. Adding COUNT/SUM crosses from "relationship traversal" into "analytics query" — a DSL boundary the project explicitly rejects. Revisit after measured demand. |
| Is sorting worth doing with aggregation? | **Sorting is worth doing independently.** It's orthogonal to aggregation and enables meaningful `limit` (e.g., "top 5 worst maintenance records"). Trivial implementation (`sorted()` on already-joined rows). No DSL creep. |
| Minimum deliverable scope? | **R3E1: ORDER BY only.** No aggregation, no GROUP BY, no COUNT/SUM/AVG. |

### 1.2 Rationale

The current traverse pipeline already produces the full matched row set in memory
before paging. Sorting is a one-line `sorted(matched, key=...)` call. It adds
real user value (top-N queries, ordered display) without opening the aggregation
floodgate. Aggregation requires new response shapes, new audit metadata, and a
fundamentally different output model — it is a separate product decision, not a
natural extension of traversal.

---

## 2. Recommendation

**Do R3E1 (sorting only). Skip R3E2 (aggregation) indefinitely.**

If sorting proves popular and users ask for "count per group," reconsider
aggregation as a separate design gate — not as R3E2, but as a fresh evaluation
against the DSL guardrails.

---

## 3. Proposed Scope and Boundaries

### 3.1 R3E1 — ORDER BY (Recommended)

#### Request Extension

```python
# RuntimeTraverseRequest — new optional field
order_by: list[OrderByClause] | None = Field(default=None)

class OrderByClause(BaseModel):
    field: str   # "{ot}__{prop}" prefixed field name, e.g. "maintenance__downtime_hours"
    direction: str = Field(default="asc", pattern="^(asc|desc)$")
```

**Constraints:**
- `field` must reference a **selected** field (in `fields[ot]`). Sorting by unselected fields is rejected with 422.
- `field` format is `{ot}__{prop}` (the same flat prefix convention used in output rows).
- `direction` is `"asc"` or `"desc"` (default `"asc"`).
- Multiple `order_by` entries are allowed. Stable sort (Python `sorted()` → `list.sort()` is stable).
- Sorting is applied after join/filter, **before** offset/limit.
- Sorting by FK/PK join columns is rejected (these are internal, not user-facing).

#### Semantics

```
stream rows → type-convert → filter → sort → offset → limit → serialize
```

Current pipeline:
```
join → filter → [offset → limit] → serialize
```

R3E1 pipeline:
```
join → filter → sort → [offset → limit] → serialize
```

Sorting runs on the flat joined dicts (`{ot}__{prop}` keys). For grouped
responses, sorting runs on the flat rows **before** grouping, so groups appear
in sorted order of their root OT fields.

#### Explain Extension

```python
# TraverseExplain gains one optional field
order_by: list[dict] | None = None
# Each dict: {"field": "maintenance__downtime_hours", "direction": "desc"}
```

Explain records `order_by` metadata (field names and directions). No data values
are exposed — field names are contract metadata, not user data.

#### Audit

Existing `field_names` and `filter_field_names` columns already capture which
fields the query touched. Sorting does not touch new fields — it operates on
already-selected fields. **No new audit columns needed.**

Audit `error_code` additions (two new codes):
- `invalid_sort_field` — field not in selected fields or is FK/PK internal
- `invalid_sort_direction` — direction not "asc" or "desc" (Pydantic catches this at 422, so this is defense-in-depth)

#### Interaction with Existing Features

| Feature | Interaction |
|---------|-------------|
| `response_shape="flat"` | Sort flat rows by `{ot}__{prop}` keys. Works naturally. |
| `response_shape="grouped"` | Sort flat rows before grouping. Root groups appear in sorted order of root OT fields. Child ordering within groups is NOT affected by sort (child order follows join order). |
| `direction="reverse"` | Sort operates on already-reversed joined rows. No special handling needed. |
| `filters` | Sort runs after filter. Filtered-out rows don't participate in sort. |
| `limit`/`offset` | Sort → offset → limit. "Top 5" semantics work correctly. |
| `explain_only` | Records `order_by` in explain. No data reads. |
| Two-hop | Sort on any selected field across all three OTs. |

#### Test Scope (~8-10 tests)

1. Single `order_by` asc on a field → rows in ascending order
2. Single `order_by` desc → rows in descending order
3. Multiple `order_by` keys → secondary sort when primary ties
4. `order_by` + `limit=5` → top 5 rows
5. `order_by` + `response_shape="grouped"` → groups in sorted order
6. `order_by` on non-selected field → 422
7. `order_by` on FK/PK internal field → 422
8. `order_by` with invalid direction → 422 (Pydantic)
9. `explain_only` with `order_by` → metadata in explain
10. Two-hop sort works across OTs

#### Explicit Non-Goals

- ❌ Sorting by aggregate values (needs aggregation first — R3E2).
- ❌ Sorting within grouped children (only root-level ordering).
- ❌ Null-handling policy (NULLs sort first/last — don't specify; Python's default is fine for v1).
- ❌ Expression-based sort keys (no `"maintenance__downtime_hours * 2"`).
- ❌ Case-insensitive sort toggle (use Python default).

---

### 3.2 R3E2 — COUNT Aggregation (Deferred, Design Only for Reference)

If aggregation is ever approved, this is the **minimum bounded design**.

#### Request Extension

```python
aggregations: list[AggregationClause] | None = Field(default=None)

class AggregationClause(BaseModel):
    function: str = Field(pattern="^count$")  # ONLY "count" in v1
    alias: str = Field(min_length=1, max_length=60)
```

#### Semantics

- Only valid with `response_shape="grouped"`. Flat response + aggregation → 422.
- COUNT counts child rows within each root group.
- Result: each root group object gains `_aggregates: {alias: value}` field.
- Example: `equipment → maintenance` with `aggregations=[{function:"count", alias:"maint_count"}]`

```json
{
  "rows": [{
    "equipment": {"name": "Pump-A"},
    "_aggregates": {"maint_count": 2},
    "maintenance": [...]
  }]
}
```

#### Explain Extension

```python
aggregations: list[dict] | None = None
# Each dict: {"function": "count", "alias": "maint_count"}
```

#### Audit

No new columns. `field_names` unchanged (aggregation doesn't select new fields).
`row_count` still reflects root-level group count.

#### Explicit Non-Goals (even if R3E2 is done)

- ❌ SUM, AVG, MIN, MAX functions.
- ❌ GROUP BY arbitrary fields (group is always root OT).
- ❌ HAVING clause.
- ❌ Cross-OT aggregation expressions.
- ❌ Aggregation on flat response.
- ❌ Nested/sub aggregations.
- ❌ Window functions.

**Decision gate for R3E2:** Must demonstrate ≥2 concrete user stories that
cannot be satisfied by client-side counting on the grouped response. "It would
be nice" is not sufficient — show a real pilot workflow that breaks without it.

---

## 4. Forbidden Items (Hard Boundaries)

These apply regardless of which R3E slice is implemented:

1. **No expression strings.** All parameters are structured JSON scalars and enums.
   No `"sort": "downtime_hours DESC"` as a string.
2. **No arbitrary WHERE/HAVING DSL.** Equality filters only (existing R2/R3C model).
   No `>`, `<`, `!=`, `LIKE`, `IN`, `BETWEEN`.
3. **No cross-OT computation expressions.** Sorting by `"equipment__status"` is OK.
   Sorting by `"maintenance__downtime_hours - equipment__threshold"` is NOT.
4. **No joins beyond traverse path.** The path IS the join. No `JOIN` syntax.
5. **No write operations.** Traverse remains read-only.
6. **No sub-queries or nesting.** `order_by` cannot reference aggregate aliases.
   `aggregations` cannot contain sub-aggregations.
7. **No custom functions or UDFs.** Function set is a fixed Pydantic-validated enum.

---

## 5. Recommended Sequencing

```
R3D (delivered) → R3E1 (sorting, Standard) → R3F (FK indexing, Standard)
                                              ↘ R3E2 (aggregation, gated — skip for now)
```

**Rationale:**
- R3E1 sorting is a natural complement to limit/offset. It makes the existing
  pagination parameters useful beyond "first N rows."
- R3F FK indexing is a performance concern that can be scoped independently.
- R3E2 aggregation should not block R3F. It is a separate product decision.

---

## 6. DSL Creep Guardrail Checklist

Before any R3E implementation begins, confirm:

| Guardrail | R3E1 Sorting | R3E2 Aggregation |
|-----------|-------------|------------------|
| No expression strings | ✅ Structured `{field, direction}` objects | ✅ Structured `{function, alias}` objects |
| No cross-OT expressions | ✅ Field references are prefixed literals | ✅ COUNT operates on known child rows |
| No arbitrary WHERE/HAVING | ✅ N/A (sorting only) | ✅ No HAVING clause |
| Bounded function set | ✅ Fixed enum `asc/desc` | ✅ Only `count` |
| Explain, don't optimize | ✅ `order_by` metadata in explain | ✅ `aggregations` metadata in explain |
| No query planner | ✅ Trivial `sorted()` call | ✅ Trivial `len()` call |
| Review gate passed | ✅ This document | ❌ Needs separate design gate |

---

## 7. Files to Update (if recommendation is accepted)

| File | Change |
|------|--------|
| `docs/r3e-aggregation-sorting-design.md` | This document (created) |
| `docs/agent-handoff.md` | Add R3E design decision entry |
| `docs/project-status.toml` | Update `next_decision_gate` to reflect R3E1 sorting decision |
| `docs/r3-relationship-runtime-enhancement-planning.md` | Add forward reference to this doc |

**Not changed:** No Python files, no tests, no schemas, no models, no migrations.

---

## 8. Ready for Codex Review

- [ ] Summary answers all three design questions
- [ ] Boundaries: no SQL/DSL creep, no expression strings, no cross-OT expressions
- [ ] Sequencing: R3E1 sorting → R3F → (gated) R3E2 aggregation
- [ ] Explain/audit: sorting metadata in explain, no new audit columns
- [ ] Non-goals: no aggregation in v1, no GROUP BY, no HAVING
- [ ] Forbidden items: all six hard boundaries documented
- [ ] Status file: `project-status.toml` next gate adjusted, not marked delivered
