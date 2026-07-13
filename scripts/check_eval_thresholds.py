"""Threshold guard for retrieval eval reports.

Usage:
    .venv/Scripts/python scripts/check_eval_thresholds.py .tmp/retrieval_eval_report.json --min-recall5 0.6
    .venv/Scripts/python scripts/check_eval_thresholds.py .tmp/retrieval_eval_report.json --baseline .tmp/baseline.json

Exit 0 if all thresholds pass, exit 1 if any fail.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def check(
    report_path: str,
    min_recall5: float = 0.0,
    max_noresult: float = 1.0,
    baseline_path: str | None = None,
    *,
    min_mrr: float = 0.0,
    min_citation_correctness: float = 0.0,
    min_faithfulness: float = 0.0,
    min_refusal_accuracy: float = 0.0,
    require_safety: bool = False,
) -> int:
    report = json.loads(Path(report_path).read_text(encoding="utf-8"))
    methods = report.get("methods", {})
    failures = 0

    if "keyword" not in methods:
        print("FAIL: no 'keyword' method in report")
        return 1

    kw = methods["keyword"]
    r5 = kw.get("recall_at_5", 0)
    mrr = kw.get("mrr", 0)
    nr = kw.get("no_result_rate", 0)

    if r5 < min_recall5:
        print(f"FAIL: keyword Recall@5 = {r5} < {min_recall5}")
        failures += 1
    else:
        print(f"PASS: keyword Recall@5 = {r5} >= {min_recall5}")

    if nr > max_noresult:
        print(f"FAIL: keyword No-Result Rate = {nr} > {max_noresult}")
        failures += 1
    else:
        print(f"PASS: keyword No-Result Rate = {nr} <= {max_noresult}")

    checks = [
        ("keyword MRR", mrr, min_mrr),
        (
            "citation correctness",
            report.get("rag_metrics", {}).get("citation_correctness", 0),
            min_citation_correctness,
        ),
        (
            "faithfulness",
            report.get("rag_metrics", {}).get("faithfulness", 0),
            min_faithfulness,
        ),
        (
            "refusal accuracy",
            report.get("rag_metrics", {}).get("refusal_accuracy", 0),
            min_refusal_accuracy,
        ),
    ]
    for label, actual, minimum in checks:
        if actual < minimum:
            print(f"FAIL: {label} = {actual} < {minimum}")
            failures += 1
        else:
            print(f"PASS: {label} = {actual} >= {minimum}")

    if require_safety:
        safety = report.get("safety", {})
        safety_passed = safety.get("passed") is True
        categories_match = safety.get("passed_categories") == safety.get("total_categories", 0)
        if not safety_passed or not categories_match:
            print(
                "FAIL: safety scenarios = "
                f"{safety.get('passed_categories', 0)}/{safety.get('total_categories', 0)}"
            )
            failures += 1
        else:
            print(
                "PASS: safety scenarios = "
                f"{safety['passed_categories']}/{safety['total_categories']}"
            )

    if baseline_path:
        baseline = json.loads(Path(baseline_path).read_text(encoding="utf-8"))
        if "keyword" in baseline.get("methods", {}):
            bk = baseline["methods"]["keyword"]
            br5 = bk.get("recall_at_5", 0)
            bmrr = bk.get("mrr", 0)
            drop = br5 - r5
            if drop > 0.05:
                print(f"WARN: keyword Recall@5 dropped by {drop:.3f} vs baseline {br5}")
            else:
                print(f"PASS: keyword Recall@5 stable (Δ = {drop:+.3f})")
            mrr_drop = bmrr - kw.get("mrr", 0)
            if mrr_drop > 0.05:
                print(f"WARN: keyword MRR dropped by {mrr_drop:.3f} vs baseline {bmrr}")

    if failures:
        print(f"\n{failures} threshold(s) FAILED")
    else:
        print("\nAll thresholds PASSED")
    return 1 if failures else 0


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="RAG eval threshold guard")
    p.add_argument("report", help="Path to JSON eval report")
    p.add_argument("--min-recall5", type=float, default=0.6, help="Minimum keyword Recall@5")
    p.add_argument("--max-noresult", type=float, default=0.2, help="Maximum no-result rate")
    p.add_argument("--baseline", help="Path to baseline JSON for regression comparison")
    p.add_argument("--min-mrr", type=float, default=0.0, help="Minimum keyword MRR")
    p.add_argument("--min-citation-correctness", type=float, default=0.0)
    p.add_argument("--min-faithfulness", type=float, default=0.0)
    p.add_argument("--min-refusal-accuracy", type=float, default=0.0)
    p.add_argument("--require-safety", action="store_true")
    args = p.parse_args()
    sys.exit(check(
        args.report,
        args.min_recall5,
        args.max_noresult,
        args.baseline,
        min_mrr=args.min_mrr,
        min_citation_correctness=args.min_citation_correctness,
        min_faithfulness=args.min_faithfulness,
        min_refusal_accuracy=args.min_refusal_accuracy,
        require_safety=args.require_safety,
    ))
