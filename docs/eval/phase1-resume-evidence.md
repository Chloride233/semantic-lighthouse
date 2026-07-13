# Phase 1 Resume Evidence

## Delivered Slice

Built a reproducible citation-grounded RAG evaluation set with 65 unique
questions over 15 offline enterprise AI knowledge documents: 60 answerable
gold questions and 5 explicit no-evidence questions.

Each evaluation item records:

- the user question
- a gold reference answer
- the expected source document title
- the source fixture path
- a verbatim evidence quote
- whether the expected behavior is an evidence-gated refusal

Automated contract tests reject datasets outside the 50-100 item range,
duplicate IDs, empty reference answers, missing evidence, title/source mismatch,
missing fixture files, and quotes that cannot be found in the declared source.

## Verifiable Evidence

- Implementation: commit `f3f52a8`
- Metric implementation: commit `08463a4`
- Dataset: `tests/eval/queries.json`
- Contract tests: `tests/test_eval.py`
- Targeted verification: 8 passed
- Full regression: 1120 passed, 3 skipped
- Browser E2E included in full regression: 18 passed
- Ruff: all checks passed for `src` and `tests`

## Offline Baseline

Run with:

```bash
.venv/bin/python scripts/run_eval.py --output .tmp/phase1-metrics.json --markdown .tmp/phase1-metrics.md
```

Measured results:

| Metric | Result |
|---|---:|
| Keyword Recall@3 | 0.933 |
| Keyword Recall@5 | 0.950 |
| Keyword MRR | 0.901 |
| Hybrid Recall@3 | 0.933 |
| Hybrid Recall@5 | 0.950 |
| Hybrid MRR | 0.901 |
| Semantic Recall@5 | 0.000 |
| Citation correctness | 0.217 |
| Faithfulness proxy | 0.340 |
| Refusal accuracy | 1.000 |

Citation correctness is the fraction of returned citations whose title matches
the gold source title. Faithfulness is deterministic answer-token coverage by
the returned citation snippets, using English tokens and Chinese character
trigrams. It is not an LLM-as-judge score.

## Resume-Ready Statement

Built a 65-question citation-grounded RAG evaluation suite across 15 enterprise
AI documents, including 60 gold-answer and 5 evidence-gated refusal cases;
measured Recall@5 0.950, MRR 0.901, citation correctness 0.217,
deterministic faithfulness 0.340, and refusal accuracy 1.000, with 1,120 tests
passing across the repository.

## Claim Boundary

This slice proves deterministic offline measurement and exposes a weak citation
precision/faithfulness baseline. Fake embeddings produce semantic Recall@5 of
0.000, so vector quality and hybrid uplift are not yet valid claims. Real-provider
quality and adversarial safety results remain pending later Issue #1 items.
