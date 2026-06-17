# RAG Quality Evaluation v1 — Baseline Report

**Date**: 2026-06-17
**Phase**: Phase 1.3 "Retrieval Evaluation Harness"
**Status**: Baseline; metrics populated by scripts, not hand-written

## Corpus

| Property | Value |
|----------|-------|
| Seed documents | 15 (tests/eval/fixtures/*.md) |
| Gold queries | 20 (tests/eval/queries.json) |
| Embedding provider | fake (8-dim random) |
| Chat provider | fake (template) |
| Retrieval methods | keyword (w=1.0), semantic (w=0.0), hybrid (w=0.3) |

## Ontology KB Quality Audit

| Property | Value |
|----------|-------|
| Real knowledge base | F:\ontology-kb\knowledge-graph (74 docs) |
| Audit questions | 10 (built-in QUALITY_QUESTIONS) |
| Eval queries (new) | 24 (docs/eval/rag-queries-ontology.json, 7 types) |

## Retrieval Metrics

_Populated by `scripts/run_eval.py --output .tmp/retrieval_eval_report.json --markdown .tmp/retrieval_eval_report.md`_

## Output Contract Audit

_Populated by `scripts/run_rag_quality_eval.py`_

## Known Limitations

- **fake embeddings**: semantic and hybrid metrics are lower-bound estimates. Keyword is the primary gate.
- **15-doc corpus**: recall metrics are coarse. Larger corpus deferred to Phase 2.5.
- **no LLM judge**: answer faithfulness not automated. Deferred to Phase 3.
- **document-level annotation**: `expect_relevant_doc_ids` uses document matching, not chunk-level.

## Next Steps

1. Run `scripts/run_eval.py --output .tmp/retrieval_eval_report.json --markdown .tmp/retrieval_eval_report.md`
2. Gate with `scripts/check_eval_thresholds.py .tmp/retrieval_eval_report.json`
3. Run `scripts/run_rag_quality_eval.py --queries docs/eval/rag-queries-ontology.json` for ontology eval
4. When real embeddings available (Phase 1.5), re-run and compare semantic/hybrid
