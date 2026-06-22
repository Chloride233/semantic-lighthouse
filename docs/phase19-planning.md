# Phase 19 — Ontology Operationalization with Realistic Business Data

**Status**: In progress (19.1 delivered, 19.2 delivered, 19.3 delivered)

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
- **Rule Validation v1**: deferred to 19.4 as script-level / offline validation.

## Slices

| Slice | Name | Status |
|-------|------|--------|
| 19.1 | Manufacturing Data Pack Contract & Validation | Delivered |
| 19.2 | FDE Demo Smoke Reads Data Pack Contract | Delivered |
| 19.3 | Mapping Contract v1 (offline/script-level) | Delivered |
| 19.4 | Rule Validation v1 (offline/script-level) | Planned |
| 19.5 | Governance Feedback v1 | Planned |
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

## AdventureWorks Note

AdventureWorks (Microsoft's OLTP sample database) is an excellent external
benchmark for manufacturing/supply-chain ontology modeling. It is **not**
part of 19.1 or 19.2. A future slice may evaluate it as a separate
data-source candidate with its own ingestion and contract validation,
not mixed into the existing synthetic generator.
