"""Run the reproducible Phase 1 RAG evaluation and enforce its quality gate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from check_eval_thresholds import check
from run_eval import _generate_markdown, run_eval


def main(json_path: Path, markdown_path: Path) -> int:
    report = run_eval()
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(_generate_markdown(report), encoding="utf-8")
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {markdown_path}")
    return check(
        str(json_path),
        min_recall5=0.90,
        max_noresult=0.0,
        min_mrr=0.85,
        min_citation_correctness=0.19,
        min_faithfulness=0.29,
        min_refusal_accuracy=1.0,
        require_safety=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Phase 1 RAG evaluation regression gate")
    parser.add_argument("--json", type=Path, default=Path(".tmp/phase1-eval-report.json"))
    parser.add_argument("--markdown", type=Path, default=Path(".tmp/phase1-eval-report.md"))
    args = parser.parse_args()
    raise SystemExit(main(args.json, args.markdown))
