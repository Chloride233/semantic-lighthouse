# Phase 14: Business Pilot Project ← Data → Model → Validate → Pilot

**Status**: 14.1–14.2 delivered. Backend Review A complete. 14.3 next.

Phase 14 shifts Semantic Lighthouse from parallel product features (RAG, Agent, Ontology drafts, tasks) toward a guided business pilot main chain. A group workspace contains one or more business pilot projects, each progressing through a fixed five-stage pipeline:

```text
goal → data → model → validate → pilot
```

Each stage is backend-controlled. Clients cannot skip, reverse, or directly set stage.

---

## Five-Stage Main Chain

| Stage | Meaning | Entry Gate |
|-------|---------|------------|
| **goal** | Business goal defined (problem_first or data_first) | Project created |
| **data** | Dataset loaded, profiled, and schema understood | Dataset assets provisioned + basic profiling |
| **model** | Ontology model (object types, properties, relations, actions) drafted from data | Data profile + Phase 12 package available |
| **validate** | Model validated against data; quality gates checked | Model package built + quality PASS/WARN |
| **pilot** | Pilot execution with measurable business outcome | Validation gate passed |

---

## Slices

| Slice | Task | Status |
|-------|------|--------|
| 14.1 | Business Pilot Project Foundation — model, API, permissions, stage helper | ✅ Delivered |
| 14.2 | Dataset Asset — dataset upload, basic profiling, data stage advancement | ✅ Delivered |
| 14.3 | Data-to-Model Bridge — link dataset profile to modeling draft generation | **Next** |
| 14.4 | Model Validation Gate — quality gate enforcement before validate stage | Planned |
| 14.5 | Pilot Execution Baseline — pilot stage status, outcome recording | Planned |

---

## 14.2 Delivered

- **Model**: `DatasetAsset` — id, group_id, project_id, original_name, storage_path, file_format (csv/xlsx), file_size, content_hash, status, row_count, column_count, profile_json, created_by, timestamps. Migration `0019`. Unique constraint on (project_id, content_hash).
- **API**: `POST/GET /groups/{gid}/projects/{pid}/datasets`, `GET/POST archive`. Member read, owner/admin upload/archive. Multipart form upload with `file` + `include_sample_values` boolean. Deduplication by content hash — duplicate uploads return `deduplicated: true` with existing asset.
- **Profiling**: CSV (stdlib csv, UTF-8/UTF-8-SIG, quoted fields) + XLSX (openpyxl read_only/data_only, first visible sheet). Metadata-first: profile_json stores column name, inferred_type, null_count, distinct_count, PK candidates, FK suggestions. Never stores raw rows.
- **Privacy**: Sample values opt-in via `include_sample_values`, capped at 3 per column, PII-masked (email, phone, ID card).
- **Safety limits**: Row scan cap (env `DATASET_MAX_SCAN_ROWS`, default 10k), distinct cap (env `DATASET_MAX_DISTINCT_VALUES`, default 1k), file size cap (`MAX_DOCUMENT_UPLOAD_BYTES`, default 50 MiB). File paths sanitized and scoped to `dataset-storage/{gid}/{pid}/{did}/`.
- **Stage advancement**: First ready asset advances project from goal→data via `advance_stage()` helper.
- **Tests**: 53 tests covering profiling (CSV/XLSX/PII/FK/hash), API (CRUD/permissions/dedup/stage/archive), and error paths.
- **Not in scope**: LLM model suggestions, Ontology draft/relation creation, Object Runtime, .xls support, frontend, delete/recover.

---

## 14.1 Delivered

- **Model**: `BusinessProject` — id, group_id, name, business_goal, entry_mode (problem_first/data_first), industry_template, stage (goal→pilot), status (active/archived), created_by, timestamps. Migration `0018`.
- **API**: `POST/GET /groups/{gid}/projects`, `GET/PATCH /groups/{gid}/projects/{pid}`, `POST .../{pid}/archive`. Member read, owner/admin write/archive. Cross-group 404.
- **Stage helper**: `services/projects.py` — `next_stage()` and `advance_stage()`. Sequential only, no skip/reverse. Unit tested.
- **Tests**: 57 tests covering CRUD, permissions, cross-group isolation, field validation, archive idempotency, stage helper.
- **Not in scope**: DatasetAsset, data upload, profiling, model bridging, Object Runtime, SDK, MCP, frontend, delete/recover.

---

## Deliberate Boundaries

- No delete or recover — projects are archived, not destroyed.
- Stage is server-managed — clients see it read-only.
- Industry template is a hint, not a validated enum — no cross-project template enforcement.
- Old features (RAG, Agent, Ontology drafts, tasks) remain as parallel capabilities. Phase 14 does not remove them.
- Frontend deferred to Kimi; CC backend-only.
