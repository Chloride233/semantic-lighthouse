"""Convert a filled governance review decision CSV into decision JSON.

This script performs structural conversion only. Validation remains owned by
precheck_governance_review_decisions.py, and accepted changes remain owned by
apply_governance_review_decisions.py.

Usage:
  .venv/Scripts/python scripts/convert_governance_decision_csv.py \
      --csv .tmp/adventureworks-semantic/governance_review_decisions_template.csv \
      --output .tmp/adventureworks-semantic/governance_review_decisions.json
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


DECISION_VERSION = "1.0"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _clean(value: str | None) -> str:
    return (value or "").strip()


def _decision_from_row(row: dict[str, str]) -> dict[str, str] | None:
    decision = _clean(row.get("decision"))
    if not decision:
        return None
    return {
        "review_item_id": _clean(row.get("review_item_id")),
        "decision": decision,
        "reviewer": _clean(row.get("reviewer")),
        "reviewed_at": _clean(row.get("reviewed_at")),
        "rationale": _clean(row.get("rationale")),
    }


def convert_governance_decision_csv(
    csv_path: Path,
    output_path: Path,
    review_batch: str = "csv-review",
) -> dict:
    if not csv_path.is_file():
        raise FileNotFoundError(f"{csv_path.name} not found at {csv_path}")

    submitted_decisions = []
    skipped_blank_rows = 0
    with csv_path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            decision = _decision_from_row(row)
            if decision is None:
                skipped_blank_rows += 1
                continue
            submitted_decisions.append(decision)

    result = {
        "decision_version": DECISION_VERSION,
        "pipeline": "governance_review_decision_csv",
        "generated_at": _utc_now(),
        "review_batch": review_batch,
        "source_artifacts": {
            "governance_review_decisions_csv": str(csv_path),
        },
        "summary": {
            "submitted_decisions": len(submitted_decisions),
            "skipped_blank_rows": skipped_blank_rows,
            "writes_to_database": False,
            "creates_real_governance_issues": False,
        },
        "decisions": submitted_decisions,
        "boundaries": {
            "offline_only": True,
            "writes_to_database": False,
            "creates_real_governance_issues": False,
            "applies_model_changes": False,
            "publishes_model_package": False,
            "hard_reasoning_allowed": False,
            "requires_human_review": True,
            "auto_accepts_candidates": False,
        },
    }
    _write_json(output_path, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convert filled governance review decision CSV to JSON",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        required=True,
        help="Filled governance_review_decisions_template.csv path",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=(
            "JSON output path "
            "(default: <csv parent>/governance_review_decisions.json)"
        ),
    )
    parser.add_argument(
        "--review-batch",
        default="csv-review",
        help="Review batch label written to governance_review_decisions.json",
    )
    args = parser.parse_args()

    output = args.output or (args.csv.parent / "governance_review_decisions.json")
    try:
        result = convert_governance_decision_csv(
            args.csv,
            output,
            args.review_batch,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    summary = result["summary"]
    print("=== Governance Review Decision CSV Conversion ===\n")
    print(f"CSV: {args.csv}")
    print(f"Submitted decisions: {summary['submitted_decisions']}")
    print(f"Skipped blank rows: {summary['skipped_blank_rows']}")
    print(f"JSON: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
