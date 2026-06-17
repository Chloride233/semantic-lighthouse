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


def check(report_path: str, min_recall5: float = 0.0, max_noresult: float = 1.0,
          baseline_path: str | None = None) -> int:
    report = json.loads(Path(report_path).read_text(encoding="utf-8"))
    methods = report.get("methods", {})
    failures = 0

    if "keyword" not in methods:
        print("FAIL: no 'keyword' method in report")
        return 1

    kw = methods["keyword"]
    r5 = kw.get("recall_at_5", 0)
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
    args = p.parse_args()
    sys.exit(check(args.report, args.min_recall5, args.max_noresult, args.baseline))
