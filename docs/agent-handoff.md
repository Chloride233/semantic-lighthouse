# Agent Handoff Snapshot

Last updated: 2026-06-24 (R3E aggregation/sorting design decision)

## State Source

**Canonical project state**: `docs/project-status.toml` — always read this first.
Detailed delivery history: `docs/archive/agent-handoff-through-phase14.md`.
This handoff is operational context, not the canonical phase tracker. If the baseline below conflicts with `docs/project-status.toml` or `git log`, treat it as historical and follow `docs/project-status.toml`.

## Latest Baseline

| Item | Value |
|------|-------|
| Commit | `58620bc` (16.1), `b5f6877` (16.2) |
| Phase 16.4 delivery commit | `d884813` |
| Backend pytest | Phase 16.1–16.2–16.4: 66/66 pass |
| ruff | clean (changed files only) |
| Migration | `0027` at head |
| Phase 16.1 outcome CRUD tests | 40 pass |
| Phase 16.2 outcome-summary tests | 13 pass |
| Phase 16.4 markdown artifact tests | 13 pass (66 total) |

## Architecture Boundaries

- **Auth**: JWT access token (15min) + httpOnly refresh cookie + rotation + replay detection. BCrypt passwords. Owner/Admin/Member roles per group.
- **Group isolation**: `group_id` enforced at DB query level on all multi-tenant resources — documents, chunks, RAG runs, conversations, tasks, Agent runs, ontology entities/relations/issues, modeling drafts, packages, projects, datasets, bindings, and project evidence links. Conversations, Tasks, and Agent runs now support immutable optional `project_id`, validated against the route group. Never trust client-supplied scope alone.
- **Agent**: Controlled coordination layer only. Deterministic backend logic (permissions, status filters, hash checks, CRUD) must not be replaced by LLM decisions. All Agent write actions require role authorization, `group_id` isolation, and user confirmation (HITL).
- **MCP**: Not started. Future candidate only — requires dedicated Safety Lane plan. See `docs/mcp-agent-boundary-design.md`.
- **Frontend**: F2 complete. Vanilla JS ES modules + hash router. Zero npm dependencies. Old pages preserved in "更多工具" dropdown.
- **No-write invariants**: MCP, Action execution, data write-back, Graph RAG — none implemented.

## Current Risks

- PDF parsing: extractable text only, no OCR.
- DOCX parsing: ordinary paragraphs only, no tables/headers/footers.
- Token usage / latency / cost not tracked in rag_runs or conversation_messages.
- No max concurrent upload session limit.
- `read_bytes()` on final parse — fine for 50 MiB, monitor on 2 GiB ECS.
- Ontology KB governance drift: `INDEX.md` / `AUTO_INDEX.md` reference `research/...` which may not exist.
- Eval drift: `docs/eval/rag-queries-ontology.json` contains expected doc IDs that do not exist in the KB.
- Bound dataset files moved/deleted on disk → query returns 422 (not silent).
- Concurrent binding generation may produce IntegrityError — handled by unique constraint.
- No caching layer — repeated queries re-read files.
- `test_conversations.py` blocked by Windows temp dir PermissionError (19 tests, pre-existing).
- `test_upload_then_ask_with_answer_card` uses forced menu-open via JS evaluation (timing workaround).

## Verification Summary

| Suite | Count | Notes |
|-------|-------|-------|
| Phase 16.1 outcomes CRUD | 40 passed | Permissions, evidence/package validation, query_refs privacy, cross-group isolation, list/read. |
| Phase 16.2 outcome-summary | 13 passed | Member read, outsider 403, cross-group 404, null-latest, uses-latest, evidence/package/runtime counts. |
| Phase 16.4 markdown artifact | 13 passed | Member read, content checks, forbidden keys, no side effects, JSON endpoint unchanged. |
| Ruff (changed files) | clean | projects.py, outcomes.py, schemas.py, test_pilot_outcomes.py |
| Migration smoke | 0027 at head | No new migration for 16.2/16.4; 0027 still at head. |
| Closeout review (2026-06-21) | PASS | All gates below checked and passed. |
| Doc alignment | PASS | 7 entry docs checked, no stale expressions |

## Phase 16 Closeout Review

**Review date**: 2026-06-21. **Reviewer**: automated closeout pass.

| Gate | Status | Detail |
|------|--------|--------|
| Permissions | ✅ | POST outcomes: owner/admin via `require_group_role`. GET outcomes/outcome-summary/outcome-artifact.md: member+ via `get_membership_or_404`. |
| Group isolation | ✅ | All queries filter `.group_id == group_id`; `_get_project_or_404` rejects cross-group. |
| Project isolation | ✅ | Evidence links validated for same project; packages validated for same project if scoped; outcome list/get queries filter `.project_id == project_id`. |
| GET side-effect-free | ✅ | `get_outcome_summary`, `get_outcome_artifact`, `list_outcomes`, `get_outcome` — all read-only, no db.add/commit. |
| Privacy | ✅ | Evidence refs: bounded `_build_provenance` (no raw_content/paths). Package refs: id/version/hash/status/count only. Query refs: recursive `_validate_query_refs_safe`. Markdown: provenance note sanitized. Artifact/summary responses contain no raw data, paths, secrets, or stack traces. |
| Sorting stability | ✅ | Latest outcome: `created_at.desc(), id.desc()`. Latest package: `created_at.desc(), id.desc()`. Latest runtime: `created_at.desc(), id.desc()`. All have stable tiebreakers. |
| No migration drift | ✅ | Only migration is 0027 (pilot_outcome_records from 16.1). No additional migrations for 16.2/16.4. |
| Test coverage | ✅ | 66 tests: 40 CRUD + 13 summary + 13 artifact. All pass. |
| Doc alignment | ✅ | `check_doc_alignment.py` PASS. `project-status.toml` latest_commit = `abb1149`. |

## Phase 17 Closeout Review

**Review date**: 2026-06-21. **Reviewer**: automated closeout pass.

| Gate | Status | Detail |
|------|--------|--------|
| Smoke script | ✅ PASS | `scripts/smoke_fde_demo.py` — 11/11 steps, 0.84s, artifact gate PASS (0 findings) |
| Seed scenario | ✅ Complete | Manufacturing equipment reliability, 4 object types, 12-column CSV spec, synthetic data only |
| Artifact quality gate | ✅ PASS | 7 required sections, 11 forbidden terms, 5 boundedness rules — 0 violations on smoke output |
| Interview script | ✅ Refreshed | `docs/interview-demo-questions.md` — FDE narrative, 5-min demo script, 5 FAQ items |
| Docs aligned | ✅ PASS | `check_doc_alignment.py` PASS, 7 entry docs |
| No code regressions | ✅ N/A | No product code changed in Phase 17 (scripts only) |
| Migration drift | ✅ Expected | `migration_head` = `0028` after Alembic version table length fix |

## Phase 18 Closeout Review

**Review date**: 2026-06-21. **Reviewer**: automated closeout pass.

| Gate | Status | Detail |
|------|--------|--------|
| Config audit | ✅ | 11 items: 8 PASS, 3 FIXED |
| PostgreSQL migration smoke | ✅ | 28/28 on pgvector/pgvector:pg17, `0028 (head)`, rerun in closeout |
| HTTP API smoke | ✅ | 9/9 PASS, ~3.4s, local uvicorn + real HTTP |
| Base-url adapter | ✅ | `--base-url` mode CLI verified |
| Artifact quality gate | ✅ | Inline in smoke_http_api |
| Docs aligned | ✅ | `check_doc_alignment.py` PASS |
| Migration drift | ✅ | `0028` at head (new migration for VARCHAR(64) fix) |
| No regressions | ✅ | Only `alembic/env.py` changed |

## Frontend Policy Realignment (2026-06-21)

The previous "frontend freeze" / "deferred to Kimi" policy has been **retired**. The new policy:
- Frontend work can re-enter future planning.
- UI/UX standard: `ui-ux-pro-max-skill` with **Minimalism & Swiss Style**.
- All future UI changes must follow lane-based verification: `verify_ui` and Playwright when code changes.
- No uncontrolled redesign or framework rewrite.
- Historical "Kimi" / "frontend freeze" references in active docs have been updated with policy notes. Archive docs retain history.

## Legacy Console Page Polish (2026-06-21)

**Status**: DOM classes wired + verify_ui PASS. `.legacyPage` wrapper added to all 6 legacy pages (Documents, Tasks, Ontology, Agent, Conversations, Groups). `.legacyFilters` with `.taskFilter`/`.docFilters` compatibility on filter bars. `.legacyTable` added to Documents and Conversations tables. `.legacyPage .grid` auto-fill layout for Groups panel grid. 53/53 verify_ui PASS, no `button:not(` selectors, all JS syntax checks pass.

**Screenshot QA update (2026-06-22)**: Added `scripts/screenshots_legacy_polish.py` to capture Documents, Tasks, Ontology, Agent, Conversations, and Groups at desktop and mobile widths. 12/12 screenshots PASS in `.tmp/legacy-polish/`; Documents page title/meta restored after visual review; no horizontal overflow reported.

## Frontend Visual Baseline Refresh (2026-06-21)

**Status**: first-pass visual refresh delivered.

- Scope: `static/styles.css` visual override layer plus `static/console.html` title/skip-link cleanup.
- Reference: Handhold-inspired typography, spacing, quiet cards, pill CTAs, and sparse Swiss layout.
- Standard: `ui-ux-pro-max-skill` Minimalism & Swiss Style. Codex environment did not expose that skill directly, so this implementation followed the documented style manually.
- Boundary: no backend/API/migration changes, no framework rewrite, no business JS rewrite.
- Verification: `scripts/verify_ui.py` 53/53 PASS; `scripts/screenshots_f2b.py` PASS with 6 screenshots in `.tmp/f2c/`; `git diff --check` clean.
- Follow-up for CC: polish remaining legacy pages and detailed component states from the new CSS override layer instead of starting a second visual system.

## Frontend Visual Closeout Review (2026-06-22)

**Status**: accepted for current baseline. Codex reviewed the 12 legacy screenshots generated by `scripts/screenshots_legacy_polish.py` across desktop and mobile. Documents, Tasks, Ontology, Agent, Conversations, and Groups render without blocking layout issues or horizontal overflow. Documents title/meta regression was fixed in `622d9de`. Ontology mobile remains dense and mobile filter stacks are visually heavy, but these are follow-up design opportunities, not closeout blockers.

**Verification**: `scripts/verify_ui.py` 53/53 PASS; `scripts/screenshots_legacy_polish.py` 12/12 PASS; `node --check static/js/pages/documents.js` PASS; `python -m py_compile scripts/screenshots_legacy_polish.py` PASS; no `button:not(` selectors; `git diff --check` clean.

## Phase 19.1 — Manufacturing Data Pack Contract & Validation

**Status**: Delivered (2026-06-22). **Lane**: Standard. **Commit**: `3b6f776`.

### Changes

- `scripts/generate_manufacturing_dataset.py`: Added `manifest.json` generation alongside existing `metadata.json`. Manifest includes generator metadata, preset/seed, per-table row_count, primary_key, foreign_keys, core_pilot flag (8 of 13 tables), and business_meaning descriptions.
- `scripts/validate_manufacturing_data_pack.py` (new): Validates a data pack directory against the 19.1 contract. 7 check categories.
- `tests/test_manufacturing_data_pack.py` (new): 6 tests — generator produces 13 tables + manifest, seed reproducibility, validator PASS on clean data, validator detects missing table, PK duplicate, and broken FK.

## Phase 19.2 — FDE Smoke Reads Manufacturing Data Pack Contract

**Status**: Delivered (2026-06-22). **Lane**: Standard.

### Changes

- `scripts/smoke_fde_demo.py`: Accepts `--data-pack <dir>` to read a manufacturing data pack manifest as its input asset contract. When omitted, auto-generates a default tiny pack. Prints manifest summary (table_count, core_pilot_count, total_rows, preset/seed, data_pack) in smoke recap. Validates manifest completeness, table count >= 13, core_pilot >= 4, row_count vs CSV, PK uniqueness.
- `tests/test_manufacturing_data_pack.py`: 4 new smoke tests — manifest summary in output, missing manifest fails, corrupt manifest fails, no-flag auto-generate stable. Total: 10 tests.

### Verification

| Check | Result |
|-------|--------|
| Smoke with --data-pack | 11/11 PASS, 0.90s, manifest summary printed |
| Smoke without --data-pack | 11/11 PASS, 0.88s, auto-generate note |
| Smoke with missing dir | exit 1, clear error message |
| Pytest (10 tests) | 10 passed, 10.07s |
| Ruff (changed files) | clean |
| Doc alignment | PASS (7 entry docs) |
| git diff --check | clean |

### Boundaries Preserved

- No UI, no backend API, no migrations, no frontend.
- No external data downloaded (AdventureWorks deferred).
- No new database dependencies (no Neo4j, OWL, LangGraph, MCP runtime, OSDK).
- Existing smoke steps unchanged; data pack is a read-only input asset.
- Mapping Contract and Rule Validation deferred to later slices (19.3, 19.4).

## Phase 19.3 — Mapping Contract v1

**Status**: Delivered (2026-06-22). **Lane**: Standard.

### Changes

- `scripts/generate_mapping_contract.py` (new): Reads `manifest.json` and deterministic column schemas to produce `mapping_contract.json`. 13 object type mappings (8 core_pilot), 15 relationship mappings (7 core_pilot). No LLM, no human interaction — purely deterministic from generator metadata.
- `scripts/validate_mapping_contract.py` (new): Validates mapping contract structure, controlled vocabularies (value_type, semantic_role, null_strategy), CSV header membership, PK/FK consistency with manifest. 32 OK / 0 FAIL on clean data.
- `tests/test_manufacturing_data_pack.py`: 6 new mapping contract tests — generate+validate PASS, missing source_column FAIL, PK mismatch FAIL, FK mismatch FAIL, invalid value_type FAIL, invalid semantic_role FAIL. Total: 16 tests.

### Mapping Contract Fields

- Per object type: `object_type`, `source_table`, `description`, `core_pilot`, `primary_key`, `column_mappings[]` (each with `source_column`, `target_property`, `value_type`, `semantic_role`, `null_strategy`, `evidence_source`).
- Per relationship: `relationship_name`, `source_table`/`source_columns`, `target_table`/`target_columns`, `cardinality`, `core_pilot`, `evidence_source`.
- Controlled vocabularies: value_type (7: string/int/float/date/datetime/bool/enum), semantic_role (11: primary_key/foreign_key/identifier/label/measure/status_flag/date_field/category/enumeration/description/reference), null_strategy (4: allow/forbid/default/unknown).

### Verification

| Check | Result |
|-------|--------|
| Contract generator | 13 object_types, 15 relationships, contract_version 1.0 |
| Contract validator (cross-validate) | 32 OK, 0 FAIL, 0 WARN — PASS |
| Pytest (16 tests) | 16 passed, 10.70s |
| Ruff (changed files) | clean |
| Doc alignment | PASS |
| git diff --check | clean |

### Boundaries Preserved

- No UI, no backend API, no migrations, no frontend.
- No database tables added — mapping_contract.json is offline-only.
- No LLM, no human interaction required for generation.
- No external data downloaded (AdventureWorks deferred).
- All mappings derived deterministically from generator metadata + TABLE_SCHEMAS.

## Phase 19.4 — Rule Validation v1

**Status**: Delivered (2026-06-22). **Lane**: Standard.

### Changes

- `scripts/validate_business_rules.py` (new): Offline deterministic business rule validation engine. Reads manifest.json + mapping_contract.json + CSV files, runs 8 rule categories, outputs `rule_validation_report.json`. No DB writes, no API calls.
- `tests/test_business_rule_validation.py` (new): 7 tests — report schema, required_field, pk_unique, fk_integrity, enum_allowed, date_order, derived_class.

### Rule Categories (8)

1. **required_field** — null_strategy=forbid columns must be non-null
2. **pk_unique** — primary keys unique and non-null
3. **fk_integrity** — foreign keys resolve to existing rows
4. **enum_allowed** — enum columns constrained to hardcoded allowed vocab (18 table.column entries)
5. **numeric_range** — 33 quantity/cost/rate/downtime/lead_time columns checked ≥0
6. **date_order** — 5 date pairs checked for start ≤ end
7. **derived_class** — 4 derived entity types identified (INFO only, never FAIL)
8. **row_count_range** — each table must have > 0 rows

### Verification

| Check | Result |
|-------|--------|
| Rule validator (clean data) | 8 rules, 4,528 checks, 103 findings (99 date_order + 4 derived_class) |
| Most rules on clean data | 7/8 PASS (date_order catches genuine generator anomalies) |
| Corrupted data (5 categories) | All detected correctly |
| Pytest (7 new tests) | 7 passed, 2.32s |
| All Phase 19 tests (19.1–19.4) | 23 passed, 13.89s |
| Ruff (changed files) | clean |
| Doc alignment | PASS |
| git diff --check | clean |

### Boundaries Preserved

- No UI, no backend API, no migrations, no frontend.
- No database writes — `rule_validation_report.json` is offline-only.
- No governance issue creation (deferred to 19.5).
- No external data downloaded (AdventureWorks deferred).
- Enum vocab hardcoded from generator schema — no runtime resolution.
- Derived class findings are INFO only — never cause exit 1.

## Phase 19.5 — Governance Feedback v1

**Status**: Delivered (2026-06-22). **Lane**: Standard.

### Changes

- `scripts/generate_governance_feedback.py` (new): Transforms rule_validation_report.json findings into governance_feedback.json — human-reviewable governance candidates grouped by type, severity, and table. 3 candidate types, 4 severity levels, specific suggested actions per rule. No DB writes.
- `tests/test_governance_feedback.py` (new): 6 tests — schema, grouping by type/severity, missing report, boundaries enforcement, --fail-on-critical, clean-data stability.

### Candidate Types

| Type | Trigger Rules | Description |
|------|--------------|-------------|
| `data_quality_issue` | required_field, pk_unique, fk_integrity, enum_allowed, numeric_range, date_order, row_count_range | Data quality problem in source CSV |
| `mapping_review` | enum_allowed, required_field, date_order | Mapping contract may need revision |
| `ontology_modeling_opportunity` | derived_class | Pattern that may warrant explicit Ontology modeling |

### Verification

| Check | Result |
|-------|--------|
| Governance generator (clean data) | 103 candidates, 99 high / 4 info |
| --fail-on-critical (clean) | exit 0 (no critical) |
| --fail-on-critical (FK broken) | exit 1 (critical candidates) |
| Pytest (6 new tests) | 6 passed, 2.44s |
| All Phase 19 tests (29) | 29 passed, 15.00s |
| Ruff (changed files) | clean |
| Doc alignment | PASS |
| git diff --check | clean |

### Closed Loop Proven

```text
CSV data → manifest.json → mapping_contract.json
→ validate_business_rules.py → rule_validation_report.json
→ generate_governance_feedback.py → governance_feedback.json
→ (future: human review → DB governance issues / modeling drafts)
```

### Boundaries Preserved

- No UI, no backend API, no migrations, no frontend.
- No database writes — governance_feedback.json is offline-only.
- No real governance_issues or modeling_drafts created.
- Human review explicitly required before any DB-level action.
- No external data downloaded (AdventureWorks deferred).

## Phase 19.6 — Closeout Review

**Status**: Complete (2026-06-22). **Lane**: Standard.

### Pipeline Verification (full chain)

```
CSV data → manifest.json → mapping_contract.json
→ validate_business_rules.py → rule_validation_report.json
→ generate_governance_feedback.py → governance_feedback.json
→ smoke_fde_demo.py --data-pack (11/11 PASS)
```

| Gate | Result |
|------|--------|
| Data pack generation | 13 tables, 279 rows |
| Data pack validation | 57 OK / 0 FAIL |
| Mapping contract generation + validation | 32 OK / 0 FAIL |
| Rule validation | 8 rules, 4,528 checks |
| Governance feedback | 103 candidates (99 high, 4 info) |
| FDE smoke (end-to-end) | 11/11 PASS, artifact gate PASS |
| Pytest (29 tests) | 29 passed, 14.93s |
| Ruff (10 files) | All clean |
| Doc alignment | PASS |

### Artifacts

5 offline JSON artifact types per data pack: manifest.json, metadata.json,
mapping_contract.json, rule_validation_report.json, governance_feedback.json.

### Boundaries Preserved

- No UI, backend API, database migrations, or frontend changes.
- All artifacts offline — no database writes.
- No governance_issues or modeling_drafts created in DB.
- No external data downloaded.
- No new technology dependencies.

### Known Follow-ups

1. **AdventureWorks external benchmark**: Separate evaluation slice with
   own ingestion and contract validation.
2. **Portfolio/demo packaging**: Final docs, demo video, cloud deployment.
3. **Safety Lane: DB-backed governance feedback**: After human review,
   write confirmed candidates as real governance_issues or modeling_drafts.

## Portfolio/Demo Packaging v1

**Status**: Delivered (2026-06-22). **Lane**: Fast (docs only).

### Changes

- `docs/portfolio-demo-narrative.md` (new): Full portfolio narrative — one-paragraph pitch, journey (Phase 8→19), architecture differentiators, demo walkthrough, audience-specific entry points.
- `README.md`: Rewritten as a public-facing portfolio entrypoint with demo commands, Phase 19 pipeline, architecture chain, capabilities, and explicit boundaries.
- `PRODUCT.md`: Updated with Phase 18–19 achievements and portfolio narrative reference.
- `docs/project-status.toml`: Focus and next gate updated.
- `docs/agent-handoff.md`: This entry.

### Key Messages

- Semantic Lighthouse is an Ontology semantic operating layer, not a generic RAG/Agent demo.
- Full offline pipeline: CSV → manifest → mapping_contract → rule_validation → governance_feedback.
- 29 tests, 5 offline artifact types, 8 rule categories, 3 governance candidate types.
- Zero external dependencies for demo — fake providers, temporary SQLite, no API keys.
- Architecture decisions are intentional: what's NOT built is as important as what IS.

### Next Candidates

1. Demo video / screenshot capture for portfolio presentation
2. Implement AdventureWorks external benchmark (see `docs/adventureworks-benchmark-planning.md`)
3. Safety Lane: DB-backed governance feedback from confirmed candidates

## P1.1 — Pilot First-Use Guidance

**Status**: Delivered (2026-06-22). **Lane**: Standard.

### Changes

- `static/js/pages/projects.js`: Empty state rewritten as guided onboarding ("从一个业务 Pilot 开始"). Dialog placeholder with concrete example. CLI demo hint.
- `static/js/pages/project.js`: Stage-by-stage guidance (5 stages). Data hint recommends core tables. Secondary hint with script path.
- `static/js/pages/project-model.js`: Stage guidance + expanded no-drafts hint.
- `static/js/pages/project-validate.js`: Stage guidance + expanded bindings hint.
- `static/js/pages/project-pilot.js`: Stage guidance for typed query.
- `static/styles.css`: `.stageGuide`, `.stageHint code`, `.emptyFooter`.

### Verification: node --check 5/5 clean, verify_ui 53/53, doc alignment PASS.

## P1.2 — Demo Dataset Onboarding

**Status**: Delivered (2026-06-22). **Lane**: Standard.

### Changes

- `src/semantic_lighthouse/routers/datasets.py`: Added `POST /demo-data` endpoint. Owner/admin only. Generates tiny manufacturing data pack via subprocess, imports 13 CSVs as project datasets. Shared `_import_single_dataset()` helper. Deduplicates by content hash.
- `static/js/pages/project.js`: "载入制造业示例数据" button in data stage. Hint text updated to mention one-click import.
- `tests/test_dataset_assets.py`: 6 new tests — owner/admin success (201, 13 datasets), member 403, outsider 403, idempotent (skip all), archived 409.

### Verification: pytest 6/6, verify_ui 53/53, ruff clean, JS syntax OK, doc alignment PASS.

### Boundaries: no migrations, no new deps, no auto-accept drafts, no auto-activate pilot.

### Codex Review Fix

- Fixed demo onboarding visibility: the "load manufacturing demo data" action is now visible at the no-dataset goal stage, not only bound in data-stage JavaScript.
- Added `verify_ui.py` coverage for the P1.2 demo data button at goal stage.
- Verification: `node --check static/js/pages/project.js`, `scripts/verify_ui.py` 54/54, `git diff --check`.

## P1.3A — First-Use Demo Data Path Smoke

**Status**: Delivered (2026-06-22). **Lane**: Standard.

### Changes

- `scripts/verify_ui.py`: Added 5 new checks (P1.3A section). Creates a separate
  Pilot, clicks loadDemoBtn, waits for import, asserts stage=数据, asserts
  ≥13 datasets, asserts genFromDataBtn visible. Uses `wait_for_selector` for
  robust timing (generator+profiling takes 5-10s).

### Verification: 59/59 verify_ui (5 new P1.3A + 54 existing), doc alignment PASS.

### No product blockers found. Demo data import works end-to-end via UI.

## R1A — Runtime Boundary Audit

**Status**: Delivered (2026-06-22). **Lane**: Standard, docs/planning only.

### Changes

- `docs/r1-runtime-boundary-audit.md` documents the current runtime boundary,
  ownership pressure in `services/runtime.py`, and the behavior-preserving
  extraction plan.
- Current decision: runtime correctness is not the blocker; maintainability and
  review risk are. Do not rewrite runtime or expand query behavior.
- Recommended next slice: R1B contract and audit extraction only.

### Boundaries

- No code changes.
- No migrations.
- No API/request/response changes.
- No query language, joins, Graph RAG, MCP runtime, Agent writes, external
  connectors, or frontend redesign.

## R1B — Contract And Audit Extraction

**Status**: Delivered (2026-06-23). **Lane**: Standard.

### Changes

- `src/semantic_lighthouse/services/runtime_contract.py` (new): `_get_latest_project_package`, `_build_contract_context` — latest package lookup and compiled contract context.
- `src/semantic_lighthouse/services/runtime_audit.py` (new): `_record_audit`, `_SANITIZED_ERROR_CODES`, `_sanitized_code` — immutable audit record creation and sanitized error codes.
- `src/semantic_lighthouse/services/runtime.py`: Removed extracted functions; imports and re-exports from `runtime_contract` and `runtime_audit`. All public entry points (`generate_bindings`, `execute_query`, `activate_pilot`) unchanged.

### Verification

| Check | Result |
|-------|--------|
| Pytest (test_project_runtime.py) | 94/94 passed, 65.87s |
| Ruff (changed files) | clean |
| Doc alignment | PASS |
| git diff --check | clean |

### Boundaries Preserved

- No router path, request body, response body, permission, or stage gate changes.
- No database model or migration changes.
- No query semantic changes.
- No new dependencies.
- No dataset IO, query core, binding, or activation extraction (deferred to R1C/R1D/R1E).
- `OntologyRuntimeAudit` kept as re-export in `runtime.py` for test backward compatibility.

## R1C — Dataset IO Extraction

**Status**: Delivered (2026-06-23). **Lane**: Standard.

### Changes

- `src/semantic_lighthouse/services/runtime_dataset_io.py` (new): `_validate_dataset_path`, `_stream_csv_rows`, `_stream_xlsx_rows`, `_read_dataset_rows` — dataset path safety validation and CSV/XLSX row streaming/reading.
- `src/semantic_lighthouse/services/runtime.py`: Removed extracted functions; cleaned `csv` and `Path` imports; imports and re-exports from `runtime_dataset_io`. All public entry points unchanged.

### Verification

| Check | Result |
|-------|--------|
| Pytest (test_project_runtime.py) | 94/94 passed, 68.35s |
| Ruff (changed files) | clean |
| Doc alignment | PASS |
| git diff --check | clean |

### Boundaries Preserved

- No router path, request body, response body, permission, or stage gate changes.
- No database model or migration changes.
- No query semantic changes.
- No new dependencies.
- No value/filter conversion or query core extraction (completed in R1D).
- No binding or activation extraction (deferred to R1E, optional).

## R1D — Query Core Extraction

**Status**: Delivered (2026-06-23). **Lane**: Standard.

### Changes

- `src/semantic_lighthouse/services/runtime_query.py` (new): `_convert_value`, `_convert_filter_value`, `execute_query`, `_DEFAULT_LIMIT`/`_MAX_LIMIT`/`_MAX_OFFSET` — value/filter type conversion and read-only query execution.
- `src/semantic_lighthouse/services/runtime.py`: Removed extracted functions and cleaned unused imports (`datetime`, `typing.Any`, `get_settings`); imports and re-exports `execute_query` for `activate_pilot` and router backward compatibility.

### Verification

| Check | Result |
|-------|--------|
| Pytest (test_project_runtime.py) | 94/94 passed, 80.81s |
| Ruff (changed files) | clean |
| Doc alignment | PASS |
| git diff --check | clean |

### Boundaries Preserved

- No router path, request body, response body, permission, or stage gate changes.
- No database model or migration changes.
- No query semantic changes (still single object_type, field whitelist, equality filters, filter-before-offset-before-limit).
- No relationship traversal, join, Graph RAG, Neo4j, SQL/DSL/AST.
- No new dependencies.
- No binding or activation extraction (R1E remains optional).
- `activate_pilot` smoke still calls the same extracted `execute_query` via re-export.

### R1 Refactor Summary

After R1B–R1D, `services/runtime.py` contains only `generate_bindings` and `activate_pilot`. The extracted modules form a clean dependency chain:

```
runtime_query → runtime_contract, runtime_audit, runtime_dataset_io
runtime.py    → runtime_query, runtime_contract, runtime_audit, runtime_dataset_io
```

No circular imports. All backward-compatible re-exports preserved.

## Four-Chain Ontology Route Alignment

**Status**: Accepted (2026-06-23). **Lane**: Fast, strategy/docs only.

### Source

- `docs/palantir-ontology-four-chain-gap-analysis.md`

### Decision

- Treat the next product route as four chains, not as "add a graph database":
  object chain, relationship chain, action chain, permission chain.
- Current project strengths: object chain and permission chain.
- Current gaps: relationship runtime traversal and controlled action/writeback.
- R1D remains useful because extracting query core prepares the codebase for
  relationship traversal.
- Do not let R1 become indefinite refactor work. After R1D, pivot to R2
  relationship runtime query unless a concrete blocker appears.

### Explicit Non-Goals For The Next Step

- No Neo4j/graph database adoption just because relationships exist.
- No Graph RAG.
- No action writeback before a separate HITL/audit design.
- No Agent/MCP write path.

## R2C — Traversal Core

**Status**: Delivered (2026-06-23). **Lane**: Standard.

### Changes

- `src/semantic_lighthouse/services/runtime_traverse.py` (new, ~300 lines): `execute_traversal()` — single-hop hash join traversal. Resolves compiled link_map FK/PK properties → binding.property_mappings → CSV/XLSX column names. Streams source dataset, builds in-memory PK index for target dataset, performs inner-join hash join. Flat output with `{object_type}__{field}` prefix. Supports fields per OT, root filters (equality, type-converted), limit/offset, explain_only. No SQL, no DSL, no Graph RAG, no audit yet.
- `tests/test_runtime_traverse.py` (new, 25 tests): 3 classes — TestSingleHopTraversal (12 happy-path + edge), TestTraversalErrors (7 error cases), TestTraverseExplainSafety (6 provenance safety). Uses synthetic CSV temp files + monkeypatched DB/services.

### Verification

| Check | Result |
|-------|--------|
| Pytest (traversal + compiler + validator + runtime) | 174/174 passed, 81.30s |
| Ruff (traversal source + test) | clean |
| Doc alignment | PASS |
| git diff --check | clean |

### Boundaries Preserved

- No router, no API endpoint, no DB migration.
- No audit (deferred to R2E).
- Single-hop only (path length == 2).
- No cross-package traversal.
- No frontend changes.

## R2D — Router And API

**Status**: Delivered (2026-06-23). **Lane**: Standard.

### Changes

- `src/semantic_lighthouse/schemas.py`: Added `RuntimeTraverseRequest`, `RuntimeTraverseResponse`, `HopExplain`, `TraverseExplain` Pydantic models. Request: path (min_length=2, max_length=2), optional fields/filters per OT, limit/offset, explain_only. Response: flat joined rows, row_count, explain block, optional type_errors.
- `src/semantic_lighthouse/routers/runtime.py`: Added `POST /groups/{gid}/projects/{pid}/runtime/traverse` endpoint. Member+ via `get_membership_or_404`. Project group/status validation (404 cross-group, 409 archived). Root OT filter extraction from nested `{ot: {field: value}}` body. Non-root filters are rejected with 422 instead of silently ignored. ValueError → 422 mapping. Type errors → 422 with detail.
- `tests/test_runtime_traverse.py`: Added 17 integration tests across 3 classes — `TestTraverseRouterPermissions` (5: member success, non-member 403, outsider 403, cross-group 404, archived 409), `TestTraverseRouterErrors` (7: no_link_type 422, invalid_fields 422, no_package 422, path too short/long 422, limit > 100 422, non-root filter 422), `TestTraverseRouterResponse` (5: explain_only, no storage_path leak, no filter value leak, no FK/PK data value leak, package/binding metadata).

### Verification

| Check | Result |
|-------|--------|
| Pytest (test_runtime_traverse.py) | 42/42 passed (25 R2C + 17 R2D), 18.98s |
| Ruff (changed files) | clean |
| Doc alignment | PASS |
| git diff --check | clean |

### Boundaries Preserved

- No DB migration, no Alembic changes.
- No audit implementation (deferred to R2E).
- No multi-hop (deferred to R2F).
- No frontend changes.
- No Graph RAG, SQL DSL, Agent/MCP, action writeback.
- Permissions mirror existing /runtime/query pattern (member+).
- Group/project isolation enforced server-side; body group/project not trusted.

## R2E — Audit And Provenance

**Status**: Delivered (2026-06-23). **Lane**: Safety.

### Changes

- `alembic/versions/0029_v29_traverse_audit_columns.py` (new): 5 nullable columns added to `ontology_runtime_audit` — `path` (JSON), `hop_count` (Integer), `link_type_api_names` (JSON), `binding_ids` (JSON), `dataset_ids` (JSON). SQLite-compatible via `batch_alter_table`.
- `src/semantic_lighthouse/models.py`: `OntologyRuntimeAudit` extended with 5 new nullable mapped columns.
- `src/semantic_lighthouse/services/runtime_audit.py`: `_record_audit()` accepts 5 new optional keyword args. `_SANITIZED_ERROR_CODES` extended with 10 traverse-specific codes.
- `src/semantic_lighthouse/services/runtime_traverse.py`: `execute_traversal()` restructured with fail-closed audit (mirrors `execute_query`). `_fail()` helper records audit + raises ValueError. Incremental collection of `audit_link_type_api_names`, `audit_binding_ids`, `audit_dataset_ids`. Flat `{ot}__{field}` prefixed field_names in audit. Success/empty/failure outcome.
- `tests/test_runtime_traverse.py`: 9 new audit tests — `TestTraverseAudit` (8) + `TestTraverseAuditFailClosed` (1). Real `db_session` + temp CSV + monkeypatched DB queries.

### Verification

| Check | Result |
|-------|--------|
| Pytest (test_runtime_traverse.py) | 52/52 passed (25 R2C + 17 R2D + 10 R2E), latest targeted run |
| Pytest (existing audit tests) | 10/10 passed |
| Ruff (8 changed files) | clean |
| Alembic smoke (SQLite temp DB) | 0029 at head, all 29 migrations OK |
| Doc alignment | PASS |
| git diff --check | clean |

### Boundaries Preserved

- No multi-hop (R2F).
- No frontend changes.
- No Graph RAG, SQL DSL, Agent/MCP, action writeback.
- Existing query/generate_bindings/activate audit untouched — 11 existing runtime audit tests pass.
- All new columns nullable — backward compat for existing audit rows.
- Filter values, storage_path, FK/PK data values never in audit (provenance verified).
- Fail-closed: audit write failure prevents data return (verified).

## R2F — Multi-Hop Traversal

**Status**: Delivered (2026-06-23). **Lane**: Safety.

### Changes

- `src/semantic_lighthouse/schemas.py`: `RuntimeTraverseRequest.path` max_length 2 → 3.
- `src/semantic_lighthouse/services/runtime_traverse.py`: `_MAX_PATH_LENGTH` 2 → 3. Path validation accepts 2–3 OTs. Two-hop branch (path_len==3) resolves all links/bindings/datasets upfront, chains two hash joins: hop 0 joins raw CSV rows (OT0→OT1), hop 1 joins intermediate flat dicts (→OT2) via new `_join_flat_rows()` helper. FK property for second hop automatically included in OT1's target index fields. Output fields stripped to user-requested only. Shared audit/explain covers full path with N hop entries. Single-hop path (len==2) unchanged.
- `tests/test_runtime_traverse.py`: 11 new `TestTwoHopTraversal` tests — basic join, field whitelist, root filter, explain (2 hops), explain_only, limit/offset, empty intermediate, empty final, no-link-type error, missing-FK error, two-hop audit metadata. Updated 3 existing tests for new path-length behavior and error messages.

### Verification

| Check | Result |
|-------|--------|
| Pytest (test_runtime_traverse.py) | **63/63 passed** (25 R2C + 17 R2D + 10 R2E + 11 R2F), 23.50s |
| Pytest (audit regression) | 11/11 passed |
| Ruff (changed files) | clean |
| Doc alignment | PASS |
| git diff --check | clean |

### Boundaries Preserved

- No DB migration needed (existing 0029 columns cover multi-hop).
- Single-hop code path unchanged — zero regression risk.
- No frontend changes.
- No Graph RAG, SQL DSL, Agent/MCP, action writeback.
- Root filters only on path[0] (same as single-hop).
- Flat `{ot}__{field}` output preserved.
- All group/project/package isolation enforced per-OT.
- Audit covers full path, all hops, all bindings, all datasets.

## R2 Closeout Review

**Status**: Complete (2026-06-23). **Lane**: Standard.

R2A-R2F are closed end-to-end: contract link_type FK/PK context, 1-2 hop
runtime traversal, REST API, audit/provenance, migration 0029, and closeout
documentation are aligned. Active docs no longer describe R2 as single-hop only.

Validation remains targeted: 63 traversal tests, 11 existing runtime audit tests,
ruff on changed runtime files, doc alignment, and `git diff --check`.

Next gate is an explicit R3 planning decision, not automatic feature expansion.

## R3A — Enhancement Planning

**Status**: Delivered (2026-06-23). **Lane**: Fast, planning/docs only.

### Changes

- `docs/r3-relationship-runtime-enhancement-planning.md` (new): Evaluates 5 R3 candidate directions — grouped response (R3B), filter pushdown (R3C), bidirectional traversal (R3D), aggregation/sorting (R3E), FK indexing (R3F). Each candidate assessed for user value, technical risk, API/schema change, DB migration need, test scope, and non-goals.
- Recommendation: R3B group_by_root response shape first. Highest demo/readability ROI, lowest risk, no migration, backward-compatible via `response_shape="flat"` default. Post-processing transformation on already-joined rows — zero change to join/auth/audit.
- Primary R3 risk identified: incremental feature accumulation must not become an ad-hoc SQL/DSL. Six guardrails defined: no expression strings, no cross-OT expressions, bounded function set, explain-only metadata, no query planner, review gate before parameterized computation slices.
- `docs/project-status.toml`: Focus updated to R3A planning delivered, next gate R3B.
- `docs/project-roadmap.md`: R3 candidate entry added.

### Boundaries

- No code, no API changes, no tests, no DB migration.
- No frontend, no MCP/Agent, no Graph RAG.
- R3B–R3F implementation deferred to explicit user decision.

## R3B — Grouped Response Shape

**Status**: Delivered (2026-06-23). **Lane**: Standard.

### Changes

- `src/semantic_lighthouse/schemas.py`: `RuntimeTraverseRequest` gains `response_shape` field (default `"flat"`, pattern `^(flat|grouped)$`). `TraverseExplain` gains `response_shape` metadata field.
- `src/semantic_lighthouse/services/runtime_traverse.py`: `execute_traversal()` accepts `response_shape` parameter. `_group_flat_rows()` (~95 lines) post-processes joined rows into nested tree: root OT fields form unique groups, child OTs nest as arrays/single-objects following hop cardinalities. `row_count` reflects group count in grouped mode. Both single-hop and two-hop branches support grouping.
- `tests/test_runtime_traverse.py`: 13 new tests — `TestGroupedResponseShape` (10: single-hop grouped, multi-root, empty, field whitelist, explain, explain_only, two-hop nested, inner-join-exclusion, two-hop explain, flat-backward-compat) + `TestGroupedResponseRouter` (3: invalid shape 422, no storage_path, no filter values).

### Verification: 76/76 tests passed, ruff clean, doc alignment PASS.

## R3D — Bidirectional Traversal

**Status**: Delivered (2026-06-24). **Lane**: Standard.

### Changes

- `src/semantic_lighthouse/schemas.py`: `RuntimeTraverseRequest` gains `direction` field (default `"forward"`, pattern `^(forward|reverse)$`). `TraverseExplain` gains `direction` metadata field.
- `src/semantic_lighthouse/routers/runtime.py`: `traverse_runtime` passes `body.direction` to `execute_traversal`. Docstring updated.
- `src/semantic_lighthouse/services/runtime_traverse.py`: `execute_traversal()` accepts `direction` parameter with validation. `_resolve_link()` accepts direction — when `"reverse"`, matches where `link.target == source_ot AND link.source == target_ot` (swapped criteria). In single-hop branch: FK/PK assignment swaps `source_fk_property`↔`target_pk_property` when reverse. In two-hop branch: per-hop FK/PK properties (stored in new `hop_fk_props`/`hop_pk_props` lists) swapped when reverse; all join/index calls use direction-aware properties. Both explain dicts include `"direction"`. Validation accepts only `"forward"` or `"reverse"`.
- `tests/test_runtime_traverse.py`: 14 new `TestBidirectionalTraversal` tests — single-hop forward unchanged, single-hop reverse from target to source, reverse with filter, reverse no-match, two-hop reverse, grouped+reverse, explain.direction forward/reverse, explain_only+reverse, invalid direction ValueError, reverse no-link error, router 200 with reverse, router 422 invalid direction, reverse permissions unchanged (403 for outsider).

### Verification

| Check | Result |
|-------|--------|
| Pytest (test_runtime_traverse.py) | **101/101 passed** (87 existing + 14 R3D), 32.83s |
| Ruff (changed files) | To be verified |
| Doc alignment | To be verified |
| git diff --check | To be verified |

### Boundaries Preserved

- No aggregation/sorting (R3E deferred).
- No per-hop direction override — one direction for the entire path.
- No SQL/DSL, no Graph RAG, no frontend, no MCP.
- No migration, no audit schema change.
- FK/PK security boundary unchanged — same inner join semantics.
- Flat/grouped response shapes both work with reverse.
- explain_only, filters, limit/offset continue to work.
- Backward compatible: default `direction="forward"` preserves all existing behavior.

## R3E — Aggregation/Sorting Design Decision

**Status**: Design-only (2026-06-24). **Lane**: Fast (no code).

### Decision

- **R3E1 sorting (ORDER BY)**: Recommended. Minimal risk, high utility. Simple
  `sorted()` call on joined rows before offset/limit. No DSL creep.
- **R3E2 aggregation (COUNT/SUM/AVG)**: NOT recommended now. Crosses from
  "relationship traversal" into "analytics query." Grouped response (R3B)
  already provides structural aggregation. Revisit after measured demand.
- **Sequencing**: R3E1 sorting → R3F FK indexing → (gated, indefinite) R3E2.

### Design Artifacts

- `docs/r3e-aggregation-sorting-design.md` — full design: request structure,
  explain/audit impact, guardrails, forbidden items, test scope.

### Key Boundaries

- Sorting by selected fields only (validated against contract).
- No expression strings, no cross-OT expressions, no aggregation in v1.
- No new audit columns — existing `field_names` covers sort metadata.
- explain gains `order_by` metadata (field names + directions).
- If aggregation is ever done: COUNT only, grouped response only, no GROUP BY,
  no SUM/AVG/MIN/MAX, no HAVING, separate design gate required.

### No code, no runtime changes, no tests, no migration, no commit.

---

## R3C — Filter Pushdown

**Status**: Delivered (2026-06-23). **Lane**: Safety.

### Changes

- `src/semantic_lighthouse/routers/runtime.py`: Removed non-root filter 422 rejection. All per-OT filters passed through to `execute_traversal()`. Docstring updated.
- `src/semantic_lighthouse/services/runtime_traverse.py`: `filters` parameter changed from flat `dict[str,value]` to per-OT `dict[str,dict[str,value]]`. New `_prepare_ot_filters()` validates/converts filters for one OT against contract + binding. New `_apply_flat_filters()` filters joined flat rows by checking `{ot}__{field}` keys. Single-hop: root filter in `_join_source_rows`, target OT filter applied after join. Two-hop: root in hop 0, OT1 filter after hop 0, OT2 filter after hop 1. `explain.filter_field_names_by_ot` and audit filter names cover all filtered OTs. AND within each OT, intersection across OTs.
- `tests/test_runtime_traverse.py`: 11 new tests — `TestFilterPushdown` (11: target OT filter, no-match, invalid field 422, explain multi-OT metadata, two-hop intermediate filter, two-hop target filter, root+intermediate intersection, root+target intersection, two-hop explain, grouped+filter, explain_only metadata). 6 existing filter calls updated from flat to per-OT format. 1 router test reversed (non-root rejection → acceptance).

### Verification: 87/87 tests passed, ruff clean, doc alignment PASS. No migration.

### Boundaries preserved: no SQL/DSL creep (structured per-OT dicts, no expression strings), no cross-OT expressions, no audit schema change, flat/grouped response shapes both work.

---

## R2B — Contract Context Extension

**Status**: Delivered (2026-06-23). **Lane**: Standard.

### Changes

- `src/semantic_lighthouse/services/business_contract_compiler.py`: Extended `LINK_FIELDS` with `source_fk_property`, `target_pk_property`. Updated `_compile_entities` link_type handler to extract both new fields.
- `src/semantic_lighthouse/services/business_contract_validator.py`: Extended `_validate_link_type()` with FK/PK property validation — source_fk_property must belong to source OT properties, target_pk_property (explicit or defaulted from OT primary_key) must belong to target OT properties, value_types must match. Built `ot_primary_keys` map in `_validate_section` and passed through `_validate_item` to `_validate_link_type`.
- `src/semantic_lighthouse/services/runtime_contract.py`: Extended `_build_contract_context()` to return `link_types` (compiled list) and `link_map` (indexed by link_type api_name, with source/target OT, cardinality, FK/PK properties, and target_pk default resolution from OT primary_key).
- `tests/test_business_contract_compiler.py`: 2 new tests — link_type with FK/PK properties compiles correctly, `_build_contract_context` includes `link_map` with correct FK/PK resolution.
- `tests/test_business_contract_validator.py`: 7 new tests — valid FK/PK passes, FK not found, explicit PK not found, target PK defaults to OT primary_key, value_type mismatch detected, value_type match accepted, link without FK/PK still passes existing checks.

### Verification

| Check | Result |
|-------|--------|
| Pytest (compiler + validator + runtime) | 149/149 passed, 109.68s |
| Ruff (changed files) | clean |
| git diff --check | clean |

### Boundaries Preserved

- No API changes, no new endpoints, no router modifications.
- No database migrations.
- No traversal execution logic (deferred to R2C).
- No frontend changes.
- Existing contracts without FK/PK annotations continue to validate and compile (new fields are optional).
- All existing runtime, compiler, and validator tests pass without modification.

---

## R2A — Relationship Runtime Query Planning

**Status**: Delivered (2026-06-23). **Lane**: Safety, design only.

### Changes

- `docs/r2-relationship-runtime-query-planning.md` (new): Complete R2 v1 design covering all 8 required questions. Key decisions: new `POST /runtime/traverse` endpoint (not extending `/runtime/query`), flat joined response with `{ot}__{prop}` prefix convention, declarative path model (ordered object_type list), filter-before-traversal semantics (filters only on root OT in v1), max 2 hops, per-hop group/project/package isolation, extended audit fields (path, hop_count, link_type_api_names, binding_ids, dataset_ids).
- `docs/project-status.toml`: Focus updated to R2A delivered, next gate R2B.
- `docs/r1-runtime-boundary-audit.md`: Added R1 closure note.
- `docs/agent-handoff.md`: This entry.

### Core Design Conclusions

1. **Relationship info lives in compiled business contract `link_types`** — validated, versioned, but NOT extracted into runtime context today (`_build_contract_context` omits link_types).
2. **Existing runtime binding is insufficient** — one binding = one OT → one dataset, no FK column concept, no cross-dataset capability.
3. **R2 v1 minimum query**: `POST /runtime/traverse` with `{"path": ["equipment", "equipment_maintenance"], "fields": {...}, "filters": {...}}`.
4. **Key prerequisite for R2B**: link_type entity must be extended with `source_fk_property` and `target_pk_property` to enable FK/PK column resolution through bindings.
5. **Implementation slices**: R2B (contract context) → R2C (traversal core) → R2D (router) → R2E (audit) → R2F (multi-hop).

### Boundaries

- No code, no migrations, no API changes, no frontend.
- No Neo4j / graph database / Graph RAG.
- No action writeback or Agent/MCP tool exposure.
- No cross-package or cross-project traversal.

### R2B Readiness

R2B can begin implementation immediately:
- Scope is narrow: extend `_build_contract_context` + compiler `LINK_FIELDS` + validator `_validate_link_type`.
- No migration, no runtime traversal logic yet.
- Existing test infrastructure (94 runtime tests) provides regression safety net.
- Risk: FK property annotation requires ontology draft schema awareness (Phase 20 follow-up). For R2B, the compiler extension is mechanical — add fields to the compiled output, validate they reference real properties.

## Next Decision Gate

**R2C complete**: Traversal core delivers single-hop hash join with FK/PK
column resolution through bindings and link_map. Next: R2D router and API
— add POST /runtime/traverse endpoint with request/response schemas,
permission wiring, and integration tests. R1E binding/activation extraction
remains optional.

## Phase 15 Delivery Summary

### 15.1 — Save Scoped RAG Answer As Project Evidence
- Owner/admin save project RAG answer via existing `POST /groups/{gid}/projects/{pid}/evidence-links`.
- evidence_type=rag_run, evidence_id=run_id. Idempotent via existing duplicate detection.

### 15.2 — Project Evidence Review Surface
- `GET /groups/{gid}/projects/{pid}/summary` surfaces recent evidence (max 5).
- Distinguishes document vs RAG run evidence in goal stage.
- Never exposes raw prompts, raw answers, paths, secrets, or stack traces.

### 15.3 — Evidence-Backed Modeling Draft Candidates
- **Slice A (backend)**: `POST /groups/{gid}/projects/{pid}/evidence-draft` — creates proposed OntologyModelingDraft from active ProjectEvidenceLink records. Derives source_rag_run_id, builds bounded evidence_refs with safe provenance. Full group/project isolation. Idempotent. 22 tests.
- **Slice B (frontend)**: Evidence selection + proposal dialog in Pilot goal stage. Owner/admin only. Checkbox selection → draft_type/name/description form → submit. Controls hidden for members and archived projects. 53/53 UI tests pass.
- **Design**: `docs/phase15.3-design.md` — no new models or migrations needed; existing OntologyModelingDraft schema already supported evidence-backed proposals.

## Key API Surfaces

- `POST /auth/register`, `/auth/login`, `/auth/refresh`, `/auth/logout`, `GET /auth/me`
- `POST /groups`, `GET /groups`, `POST /groups/{gid}/invites`, `POST /groups/join-by-invite`
- `POST /groups/{gid}/documents/import-local`, `/upload`, `/uploads/init|chunks|complete`
- `GET /groups/{gid}/documents/search`, `/semantic-search`
- `POST /groups/{gid}/rag/answer`, `GET /rag/runs`, `GET /rag/runs/{run_id}`
- `POST /groups/{gid}/projects/{pid}/rag/answer`
- `POST /groups/{gid}/conversations`, `GET /conversations`, `POST /conversations/{id}/messages`
- `POST /groups/{gid}/tasks`, `GET /tasks`
- `POST /groups/{gid}/agent/runs`, `GET /agent/runs`, `POST /agent/runs/{id}/execute|respond`
- `POST /groups/{gid}/ontology/scan`, `GET /ontology/entities|relations|issues`
- `POST /groups/{gid}/ontology/drafts`, `GET /drafts`, `POST /drafts/generate|review|review-batch`
- `POST /groups/{gid}/ontology/packages`, `GET /packages`, `GET /packages/{pid}/contract`
- `POST /groups/{gid}/projects`, `GET /projects`, `GET /projects/{pid}`
- `GET /groups/{gid}/projects/{pid}/summary`
- `GET /groups/{gid}/projects/{pid}/outcome-summary`
- `GET /groups/{gid}/projects/{pid}/outcome-artifact.md`
- `POST|GET /groups/{gid}/projects/{pid}/outcomes`, `GET /groups/{gid}/projects/{pid}/outcomes/{outcome_id}`
- `POST|GET /groups/{gid}/projects/{pid}/evidence-links`, `DELETE /groups/{gid}/projects/{pid}/evidence-links/{link_id}`
- `POST /projects/{pid}/datasets`, `GET /datasets`
- `POST /projects/{pid}/model-drafts/generate`, `GET /model-drafts/quality`
- `POST /projects/{pid}/model-drafts/packages`, `GET /packages/{pid}/contract`
- `POST /projects/{pid}/runtime/bindings/generate`, `GET /runtime/bindings`
- `POST /projects/{pid}/runtime/query`, `POST /runtime/activate`

## New Session Rules

1. Read `docs/project-status.toml` first — it is the single source of truth.
2. Declare lane at the start of every iteration (`Lane: Fast / Standard / Safety` with one-line reason).
3. Review and test before editing (depth scales with lane).
4. Keep each iteration independently usable. Prefer smallest change that closes the verified risk.
5. Do not introduce architecture the project owner cannot explain.
6. Do not add speculative abstractions for future versions.
7. Keep group-scoped data isolation as a hard invariant.
8. Do not use Agent behavior to replace deterministic backend logic.
9. Any write-like Agent/action behavior must have role authorization, group_id isolation, and user confirmation.
10. Do not let future work drift into generic RAG or generic Agent framing.
11. MCP moratorium: do not implement MCP runtime. See `docs/project-status.toml`.
12. Do not commit `.env*` (except `.example`), `*.db`, `.venv/`, `.claude/`, `__pycache__/`, build artifacts, or storage volumes.
13. Run `scripts/check_doc_alignment.py` at doc/phase boundaries.
14. Do not rely on chat history. Use `git log -1 --oneline` for the latest verified baseline.

## Quick Verification

```powershell
# Related tests (Standard Lane)
.\.venv\Scripts\python -m pytest tests/test_specific.py -p no:cacheprovider

# Full regression (Safety Lane)
.\.venv\Scripts\python -m pytest -p no:cacheprovider --ignore=tests/e2e --basetemp=.tmp\pytest-run

# Lint
.\.venv\Scripts\python -m ruff check src tests

# Doc alignment
.\.venv\Scripts\python scripts\check_doc_alignment.py

# UI smoke (frontend changes only)
.\.venv\Scripts\python scripts\verify_ui.py
```
