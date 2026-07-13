# Phase 1 Citation-Grounded RAG Evaluation Report

## Reproduce

From the repository root:

```bash
.venv/bin/python scripts/run_phase1_eval_gate.py
```

The command writes detailed JSON and Markdown artifacts to `.tmp/` and exits
non-zero when a regression threshold fails.

## Evaluation Scope

- 15 offline enterprise AI documents
- 60 answerable gold questions with reference answers and verbatim evidence
- 5 explicit no-evidence/refusal questions
- keyword, vector, and hybrid retrieval at Top-5
- deterministic fake chat provider
- evaluation-only 256-dimension English-word and CJK-trigram feature-hash vectors

## Retrieval Results

| Method | Recall@3 | Recall@5 | MRR | Precision@5 | No-result rate |
|---|---:|---:|---:|---:|---:|
| Keyword | 0.933 | 0.950 | 0.901 | 0.247 | 0.000 |
| Vector | 0.667 | 0.750 | 0.556 | 0.167 | 0.000 |
| Hybrid | 0.933 | 0.950 | 0.901 | 0.199 | 0.000 |

Keyword ranks first on the offline corpus. Hybrid matches keyword Recall@5 and
MRR but reduces Precision@5 by 0.048, so the evaluation does not support a
hybrid-uplift claim.

## Grounding Results

| Metric | Result |
|---|---:|
| Citation correctness | 0.196 |
| Faithfulness proxy | 0.293 |
| Refusal accuracy | 1.000 |

Citation correctness is the fraction of returned citation titles matching the
gold source. Faithfulness is deterministic answer-token coverage by returned
citation snippets, using English words and Chinese character trigrams. It is
not an LLM-as-judge score.

## Safety Results

| Category | Result | Evidence |
|---|---:|---|
| No evidence | 5/5 passed | Zero citations, low confidence, local evidence gate |
| Conflicting evidence | Passed | Both contradictory sources remained visible |
| Prompt injection | Passed | Injected output instruction was not followed |
| Cross-group isolation | Passed | Owned group: 1 citation; other group: 0 citations |

Residual risk: the conflicting-evidence response remains high confidence. The
system preserves contradictory sources but does not yet classify the conflict
or reduce confidence.

## Regression Gate

| Check | Threshold | Baseline |
|---|---:|---:|
| Keyword Recall@5 | >= 0.90 | 0.950 |
| Keyword MRR | >= 0.85 | 0.901 |
| Keyword no-result rate | <= 0.00 | 0.000 |
| Citation correctness | >= 0.19 | 0.196 |
| Faithfulness proxy | >= 0.29 | 0.293 |
| Refusal accuracy | >= 1.00 | 1.000 |
| Safety categories | 4/4 required | 4/4 |

The threshold checker retains its generic backward-compatible defaults. The
Phase 1 gate passes these explicit thresholds and is tested to fail when a
metric drops below its minimum.

## Claim Boundary

This report proves a reproducible offline evaluation and regression gate. The
vector baseline is lexical feature hashing rather than a neural semantic model,
and the fake chat provider does not establish real-provider answer quality or
adversarial robustness.
