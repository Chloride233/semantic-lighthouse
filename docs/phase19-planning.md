# Phase 19 — Ontology Operationalization with Realistic Business Data

**Status**: In progress (19.1–19.5 delivered)

## Goal

Operationalize the Semantic Lighthouse ontology pipeline with structured
manufacturing data that can serve as verifiable FDE demo input. Phase 19
transitions from implicit in-script seeds to a contracted data pack that
validators, tests, and demo consumers can rely on.

## Scope Boundaries

- **Industry**: Manufacturing (equipment reliability, work orders, BOM).
- **Data source**: Realistic synthetic generator (`scripts/generate_manufacturing_dataset.py`),
  generating a business-plausible data pack — not real enterprise data.
- **AdventureWorks**: Recognized as a strong external benchmark candidate but
  explicitly deferred. Not downloaded, not wired, not included in 19.1 or 19.2.
  Candidate for a future external benchmark slice.
- **No UI, no backend API changes, no migrations, no frontend.**
- **No new database dependencies** (no Neo4j, OWL, LangGraph, MCP runtime, OSDK).
- **Mapping Contract v1**: delivered as offline JSON artifact in 19.3.
- **Rule Validation v1**: delivered as offline deterministic report in 19.4.
- **Governance Feedback v1**: delivered as offline candidate generation in 19.5.
- **Phase 19 Closeout**: deferred to 19.6.

## Slices

| Slice | Name | Status |
|-------|------|--------|
| 19.1 | Manufacturing Data Pack Contract & Validation | Delivered |
| 19.2 | FDE Demo Smoke Reads Data Pack Contract | Delivered |
| 19.3 | Mapping Contract v1 (offline/script-level) | Delivered |
| 19.4 | Rule Validation v1 (offline/script-level) | Delivered |
| 19.5 | Governance Feedback v1 | Delivered |
| 19.6 | Phase 19 Closeout | Planned |

## 19.1 Delivered

- `manifest.json` contract: 13 tables, PK, FK, row_count, core_pilot, business_meaning.
- Validator (`scripts/validate_manufacturing_data_pack.py`): 7 check categories.
- Tests (`tests/test_manufacturing_data_pack.py`): 6 tests covering generation and defect detection.

## 19.2 Delivered

- `scripts/smoke_fde_demo.py` now accepts `--data-pack <dir>` to read a
  manufacturing data pack manifest as its input asset contract.
- When `--data-pack` is not provided, smoke auto-generates a default tiny pack
  and notes it in output.
- Manifest validation inside smoke: checks >= 13 tables, core_pilot >= 4,
  row_count vs CSV, PK uniqueness, CSV presence, required manifest fields.
- Smoke recap prints manifest summary: table_count, core_pilot_count,
  total_rows, preset/seed, data_pack name.
- 4 new tests: smoke reads manifest, missing manifest fails, corrupt manifest
  fails, no-flag auto-generate stable.
- Total test count: 10 (6 from 19.1 + 4 from 19.2).

## 19.3 Delivered

- `scripts/generate_mapping_contract.py` (new): Reads manifest.json and
  deterministic column schemas to produce `mapping_contract.json`.
- `scripts/validate_mapping_contract.py` (new): Validates mapping contract
  against controlled vocabularies, CSV headers, manifest PK/FK consistency.
- Contract fields per object type: `object_type`, `source_table`, `description`,
  `core_pilot`, `primary_key`, `column_mappings` (each with `source_column`,
  `target_property`, `value_type`, `semantic_role`, `null_strategy`,
  `evidence_source`).
- Relationship mappings: `relationship_name`, `source_table`/`columns`,
  `target_table`/`columns`, `cardinality`, `core_pilot`, `evidence_source`.
- Controlled vocabularies: value_type (7), semantic_role (11), null_strategy (4).
- Validator checks: contract_version, core_pilot >= 4 object_types, per-column
  controlled vocab, CSV header membership, PK/manifest consistency, FK/manifest
  consistency, evidence_source non-empty.
- 6 new tests: generate+validate PASS, missing source_column FAIL, PK mismatch
  FAIL, FK mismatch FAIL, invalid value_type FAIL, invalid semantic_role FAIL.
- Total test count: 16 (6 from 19.1 + 4 from 19.2 + 6 from 19.3).

## 19.4 Delivered

- `scripts/validate_business_rules.py` (new): Offline deterministic business rule
  validation against manifest + mapping_contract + CSV data. 8 rule categories.
- Output: `rule_validation_report.json` with summary, rule_results (per-rule
  status + findings), and boundaries section.
- 8 rule categories: required_field (null_strategy=forbid), pk_unique,
  fk_integrity, enum_allowed (hardcoded enum vocab from generator), numeric_range
  (non-negative), date_order (start <= end), derived_class (INFO-only entity
  classification), row_count_range (> 0 rows).
- Each finding: rule_id, status (PASS/FAIL/WARN/INFO), finding_id, table,
  row, primary_key, column, message, evidence (bounded — no raw data rows).
- Boundaries: offline_only=true, writes_to_database=false,
  creates_governance_issues=false.
- Enum vocab: hardcoded from generator deterministic schema (18 table.column
  entries covering status, type, priority, country, abc_class, etc.).
- Derived classes: critical_work_order, at_risk_equipment, high_value_material,
  high_scrap_work_order.
- Tests (`tests/test_business_rule_validation.py`): 7 tests — report schema,
  required_field, pk_unique, fk_integrity, enum_allowed, date_order, derived_class.
- Total test count: 23 (16 from 19.1–19.3 + 7 from 19.4).

## 19.5 Delivered

- `scripts/generate_governance_feedback.py` (new): Reads rule_validation_report.json
  and produces governance_feedback.json — groups rule findings into human-reviewable
  governance candidates. No DB writes, no real issue creation.
- Candidate types: data_quality_issue (FAIL findings), mapping_review (enum/schema
  issues), ontology_modeling_opportunity (derived_class INFO).
- Severity: critical (pk_unique, fk_integrity), high (required_field, date_order),
  medium (enum_allowed, numeric_range, row_count_range), info (derived_class).
- Each candidate: candidate_id, finding_ref, candidate_types[], severity,
  suggested_action, status=open, evidence (bounded — no raw data rows).
- CLI: --data-pack, --report, --output, --fail-on-critical.
- Boundaries: offline_only=true, writes_to_database=false,
  creates_real_governance_issues=false, replaces_human_review=false.
- Tests (`tests/test_governance_feedback.py`): 6 tests — schema, grouping,
  missing report, boundaries, --fail-on-critical, clean-data stability.
- Total test count: 29 (23 from 19.1–19.4 + 6 from 19.5).

## AdventureWorks Note

AdventureWorks (Microsoft's OLTP sample database) is an excellent external
benchmark for manufacturing/supply-chain ontology modeling. It is **not**
part of 19.1 or 19.2. A future slice may evaluate it as a separate
data-source candidate with its own ingestion and contract validation,
not mixed into the existing synthetic generator.
