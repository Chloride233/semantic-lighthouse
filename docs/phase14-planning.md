# Phase 14: Business Pilot Project ← Data → Model → Validate → Pilot

**Status**: 14.1–14.4 delivered. Backend Review B next. 14.5 pending.

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
| 14.3 | Data-to-Model Bridge — link dataset profile to modeling draft generation | ✅ Delivered |
| 14.4 | Model Validation Gate — quality gate enforcement before validate stage | ✅ Delivered |
| 14.5 | Pilot Execution Baseline — pilot stage status, outcome recording | **Next** |

---

## 14.3 Delivered

- **Migration**: `0020` — adds `project_id` (FK business_projects) and `source_dataset_id` (FK dataset_assets) to `ontology_modeling_drafts`. Nullable — legacy drafts compatible. SQLite/PostgreSQL via batch mode.
- **Schema**: `OntologyModelingDraftCreateRequest` and `OntologyModelingDraftResponse` extended with `project_id`, `source_dataset_id`. `list_drafts` supports `project_id` and `source_dataset_id` filters. New `DatasetModelingResponse` with issues list.
- **API**: `POST /groups/{gid}/projects/{pid}/model-drafts/generate` — owner/admin only. Deterministic, idempotent. Stage validation: goal→409, data→model advancement. Archived project→409. No ready datasets→400.
- **Service**: `services/dataset_modeling.py` — pure deterministic generation. Object Types (one per dataset with valid PK, api_name via `_snake_case`, display_name via `_title_case`), Properties (one per column, type-mapped: string→string, integer→integer, number→number, boolean→boolean, date→date, datetime→datetime, required=not nullable), Link Types (from project-local FK suggestions, cardinality=many_to_one). No Action Type generation.
- **Evidence**: Each draft carries `contract_profile=business_v1`, `generator=dataset_deterministic_v1`, `generation_key`, `project_id`, `source_dataset_id`. Evidence refs: dataset_id, content_hash, original_name, profile schema_version, column name, type, PK/FK role. Never includes sample_values, raw rows, or storage_path.
- **Idempotency**: `generation_key` includes project_id, dataset_id, draft_type, and normalized business key. Re-running produces no duplicates. Accepted/rejected drafts never overwritten.
- **Review chain reuse**: Existing single/batch review endpoints work on dataset-generated drafts unchanged. project_id/source_dataset_id relationships immutable during review.
- **Tests**: 27 tests covering generation (object/property/link, PK/FK, type mapping, evidence privacy, idempotency, accepted/rejected protection), permissions (owner/admin/member/outsider/cross-group), stage advancement (goal→409, data→model, no datasets→400, archived→409), project isolation, legacy CRUD/filter/review compatibility.
- **Verification**: 125 combined passed (26 drafts + 34 review + 38 contract + 27 modeling), zero legacy regressions. Migration upgrade/downgrade cycle verified.

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
