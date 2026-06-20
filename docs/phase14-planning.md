# Phase 14: Business Pilot Project ← Data → Model → Validate → Pilot

**Status**: 14.1–14.5 DELIVERED. Backend Review C / Phase 14 closeout next.

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
| **pilot** | Pilot read runtime active; bound Object Types queryable through unified contract | Activation gate: bindings valid, smoke query passed |

---

## Slices

| Slice | Task | Status |
|-------|------|--------|
| 14.1 | Business Pilot Project Foundation — model, API, permissions, stage helper | ✅ Delivered |
| 14.2 | Dataset Asset — dataset upload, basic profiling, data stage advancement | ✅ Delivered |
| 14.3 | Data-to-Model Bridge — link dataset profile to modeling draft generation | ✅ Delivered |
| 14.4 | Model Validation Gate — quality gate enforcement before validate stage | ✅ Delivered |
| 14.5 | Pilot Read Runtime + Unified Query Contract — DatasetBinding, deterministic query, pilot activation | ✅ Delivered |

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

## 14.5 Delivered — Pilot Read Runtime + Unified Query Contract

- **Model**: `OntologyDatasetBinding` (`ontology_dataset_bindings`, migration `0022`). Fields: id, group_id, project_id, package_id, dataset_id, object_type_api_name, primary_key_column, property_mappings (JSON), status (active/stale), created_by, created_at, updated_at. Unique: (package_id, object_type_api_name).
- **Binding generation**: `POST /groups/{gid}/projects/{pid}/runtime/bindings/generate` — owner/admin only. Stage must be validate or pilot. Uses latest project-scoped package (scope_key = "project:{pid}"). Deterministically maps accepted business_v1 Object Type drafts (with source_dataset_id) to DatasetAssets. Property mappings come from accepted Property drafts: property api_name → dataset column name. PK from Object Type draft's primary_key field, resolved through the matching Property draft's column evidence. Idempotent — re-running produces no duplicates. Returns structured issues on unresolvable mappings, never guesses or calls LLM. Action Types never bound. Link Types not joined.
- **Binding read**: `GET /groups/{gid}/projects/{pid}/runtime/bindings` — member+ read. Returns active bindings for the latest project package. Project existence validated, cross-group returns 404.
- **Unified query**: `POST /groups/{gid}/projects/{pid}/runtime/query` — member+ read. Restricted JSON request: object_type, optional fields (whitelist of bound property api_names), optional filters (equality only, no expressions), limit (default 20, max 100), offset (default 0, max 10000), explain_only (default false). Uses latest project package and corresponding active bindings. Only ready/non-archived datasets. Reads CSV/XLSX via controlled parsing (reuses UTF-8/UTF-8-SIG csv + openpyxl read_only/data_only patterns). File path resolved and validated to stay within dataset_storage_path/group/project. Contract value_type conversion: string→str, integer→int, number→float, boolean→True/False, date/datetime→str. Conversion errors produce explicit type_errors, never silently forge data. Results never include storage_path, sample profile, internal stack traces, or unselected columns.
- **Explain/provenance**: Explain includes package id/version/semantic_hash, binding id, dataset id/content_hash, selected fields, filter field names, limit/offset. Never includes filter values, raw rows, file paths, or secrets. explain_only=true skips data read entirely.
- **Pilot activation**: `POST /groups/{gid}/projects/{pid}/runtime/activate` — owner/admin only. Project must be validate or pilot stage. All dataset-grounded Object Types must have complete valid bindings. Datasets must be ready with ≥1 row. Smoke query (one row) executed for each binding. On full success, advances validate → pilot via existing stage helper. Idempotent — calling on pilot returns `already_pilot: true`. Any binding/dataset/data/type issue blocks advance. Ordinary query never advances stage.
- **Permissions**: member can read bindings and query. owner/admin can generate bindings and activate. outsider returns 403. cross-group/cross-project objects return 404 (no existence leak).
- **Audit**: Query audit records user/group/project/object_type, field names, filter field names, row_count, and timestamp. Never records filter values, returned data, storage_path, PII, or secrets. Existing audit model extended minimally — no generic event framework.
- **Path safety**: File storage_path resolved and verified within `dataset_storage_path/{gid}/{pid}/`. Traversal attempts rejected.
- **No MCP, no DSL/SQL, no Graph RAG**: Query uses only JSON equality filters. No expression strings, no AST, no query optimizer, no custom language. MCP runtime, SDK, and write capability remain NOT implemented — see `docs/mcp-agent-boundary-design.md`.
- **Tests**: 56 tests in `tests/test_project_runtime.py` covering binding generation (deterministic, idempotent, PK/property mapping, issues), permissions (member/owner/admin/outsider, cross-group, cross-project), query execution (field whitelist, equality filter, limit/offset, max limits), CSV and XLSX queries, contract type conversion (success and failure), explain_only, provenance sanitization, activation (validate→pilot, failure blocking, idempotency), stale package binding, path traversal rejection, and legacy backward compatibility.
- **Verification**: 216 combined tests passed (56 runtime + 57 projects + 53 datasets + 27 modeling + 23 validation). Ruff clean. Migration 0022 at Alembic head. Git diff --check clean.
- **Next**: Backend Review C / Phase 14 closeout. MCP remains post-Phase 14 candidate only.

---

## Deliberate Boundaries

- No delete or recover — projects are archived, not destroyed.
- Stage is server-managed — clients see it read-only.
- Industry template is a hint, not a validated enum — no cross-project template enforcement.
- Old features (RAG, Agent, Ontology drafts, tasks) remain as parallel capabilities. Phase 14 does not remove them.
- Frontend deferred to Kimi; CC backend-only.
- No Pilot outcome/KPI dashboard. No relation joins in query. No Action execution. No data write-back.
- No MCP server/client/SDK. No Graph RAG. No custom query language. No new dependencies added.
