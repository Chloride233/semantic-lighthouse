# Phase 1 Resume Evidence

## Delivered Slice

Built a reproducible citation-grounded RAG gold evaluation set with 60 unique
questions over 15 offline enterprise AI knowledge documents.

Each evaluation item records:

- the user question
- a gold reference answer
- the expected source document title
- the source fixture path
- a verbatim evidence quote

Automated contract tests reject datasets outside the 50-100 item range,
duplicate IDs, empty reference answers, missing evidence, title/source mismatch,
missing fixture files, and quotes that cannot be found in the declared source.

## Verifiable Evidence

- Implementation: commit `f3f52a8`
- Dataset: `tests/eval/queries.json`
- Contract tests: `tests/test_eval.py`
- Targeted verification: 8 passed
- Full regression: 1120 passed, 3 skipped
- Browser E2E included in full regression: 18 passed
- Ruff: all checks passed for `src` and `tests`

## Resume-Ready Statement

Built a 60-question gold-standard RAG evaluation set across 15 enterprise AI
documents, pairing every reference answer with a machine-verified source file
and verbatim evidence quote; added regression contracts for dataset scale,
uniqueness, schema completeness, and citation traceability, with 1,120 tests
passing across the repository.

## Claim Boundary

This slice proves evaluation-data quality and reproducibility. Recall@k, MRR,
citation correctness, faithfulness, refusal accuracy, retrieval-method uplift,
and adversarial safety results remain pending later Issue #1 acceptance items.
