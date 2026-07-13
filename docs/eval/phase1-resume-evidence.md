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
- Retrieval comparison: commit `d208491`
- Safety scenarios: commit `fe2c74e`
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
| Vector Recall@3 | 0.667 |
| Vector Recall@5 | 0.750 |
| Vector MRR | 0.556 |
| Vector Precision@5 | 0.167 |
| Hybrid Recall@3 | 0.933 |
| Hybrid Recall@5 | 0.950 |
| Hybrid MRR | 0.901 |
| Hybrid Precision@5 | 0.199 |
| Keyword Precision@5 | 0.247 |
| Citation correctness | 0.196 |
| Faithfulness proxy | 0.293 |
| Refusal accuracy | 1.000 |

Citation correctness is the fraction of returned citations whose title matches
the gold source title. Faithfulness is deterministic answer-token coverage by
the returned citation snippets, using English tokens and Chinese character
trigrams. It is not an LLM-as-judge score.

The vector baseline uses an evaluation-only deterministic 256-dimension feature
hash over English words and Chinese character trigrams. On this corpus, keyword
retrieval ranks first. Hybrid matches keyword Recall@5 and MRR but lowers
Precision@5 by 0.048, so it does not demonstrate uplift.

## Safety Evidence

| Category | Result | Evidence |
|---|---:|---|
| No evidence | 5/5 passed | Zero citations, low confidence, local evidence gate |
| Conflicting evidence | Passed | Both 30-day and 90-day policy sources returned |
| Prompt injection | Passed | `PWNED_RESPONSE` instruction was not followed; 2 grounded citations returned |
| Cross-group isolation | Passed | Secret had 1 citation in its owner group and 0 in the primary group |

Residual risk: the conflicting-evidence response remains high confidence. The
current system preserves both contradictory sources but does not yet lower
confidence or explicitly classify the conflict.

## Resume-Ready Statement

Built a 65-question citation-grounded RAG evaluation suite across 15 enterprise
AI documents, including 60 gold-answer and 5 evidence-gated refusal cases;
measured keyword Recall@5 0.950 and MRR 0.901 against a deterministic vector
baseline, showing hybrid added no recall uplift and reduced Precision@5 by
0.048; also measured citation correctness 0.196, deterministic faithfulness
0.293, refusal accuracy 1.000, and 4/4 safety categories passing with zero
cross-group citations, with 1,120 tests passing across the repository.

## Claim Boundary

This slice proves deterministic offline method comparison and exposes weak
citation precision/faithfulness. The vector baseline is lexical feature hashing,
not a neural semantic model, so real-provider vector quality remains unproven.
Conflict-aware confidence reduction and real-provider adversarial behavior remain
unproven; the current evidence covers the deterministic offline fake-provider path.
