# Phase 19 — Ontology Operationalization with Real Data

**Status**: In progress (19.1 delivered)

## Goal

Operationalize the Semantic Lighthouse ontology pipeline with structured
manufacturing data that can serve as verifiable FDE demo input. Phase 19
transitions from synthetic-seed smoke scripts to a contracted data pack
that validators, tests, and demo consumers can rely on.

## Scope Boundaries

- **Industry**: Manufacturing (equipment reliability, work orders, BOM).
- **Data source**: Synthetic generator (`scripts/generate_manufacturing_dataset.py`),
  NOT external live data.
- **AdventureWorks**: Recognized as a strong external benchmark candidate but
  explicitly deferred. Not downloaded, not wired, not included in 19.1.
  Candidates for 19.2 (planning) or 19.3 (integration).
- **No UI, no backend API changes, no migrations, no frontend.**

## Slices

| Slice | Name | Status |
|-------|------|--------|
| 19.1 | Manufacturing Data Pack Contract & Validation | Delivered |
| 19.2 | FDE Demo Smoke reads data pack contract (TBD) | Planned |
| 19.3 | AdventureWorks benchmark evaluation (TBD) | Planned |
| 19.4 | Ontology entity generation from data pack (TBD) | Planned |
| 19.5 | Phase 19 closeout (TBD) | Planned |

## 19.1 Delivered

- `manifest.json` contract: 13 tables, PK, FK, row_count, core_pilot, business_meaning.
- Validator (`scripts/validate_manufacturing_data_pack.py`): 7 check categories.
- Tests (`tests/test_manufacturing_data_pack.py`): 6 tests covering generation and defect detection.
- See `docs/agent-handoff.md` for verification details.

## AdventureWorks Note

AdventureWorks (Microsoft's OLTP sample database) is an excellent external
benchmark for manufacturing/supply-chain ontology modeling. It is **not**
part of 19.1. If Phase 19.2 or 19.3 scope it, it would be evaluated as a
separate data-source candidate with its own ingestion and contract validation,
not mixed into the existing synthetic generator.
