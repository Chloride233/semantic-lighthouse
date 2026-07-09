"""Fill selected governance review decision CSV rows with explicit decisions.

This helper writes only to the CSV file selected by the operator. It does not
infer decisions, apply decisions, write to the database, create governance
issues, publish packages, or execute runtime queries.

Usage:
  .venv/Scripts/python scripts/fill_governance_decision_csv.py \
      --csv .tmp/adventureworks-semantic/governance_review_decisions_template.csv \
      --source-table equipment \
      --derived-class at_risk_equipment \
      --decision defer \
      --reviewer ontology_steward \
      --reviewed-at 2026-07-09T08:00:00+00:00 \
      --rationale "Needs domain owner review."
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


FILL_VERSION = "1.0"
DECISION_OPTIONS = {"accept", "reject", "defer", "needs_more_evidence"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: str | None) -> str:
    return (value or "").strip()


def _read_csv(csv_path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not csv_path.is_file():
        raise FileNotFoundError(f"{csv_path.name} not found at {csv_path}")
    with csv_path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def _write_csv(
    csv_path: Path,
    fieldnames: list[str],
    rows: list[dict[str, str]],
) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _validate_inputs(
    *,
    decision: str,
    reviewer: str,
    reviewed_at: str,
    rationale: str,
    review_item_ids: list[str] | None,
    source_table: str | None,
    derived_class: str | None,
) -> None:
    if decision not in DECISION_OPTIONS:
        raise ValueError(f"invalid decision: {decision}")
    if not reviewer:
        raise ValueError("reviewer is required")
    if not reviewed_at:
        raise ValueError("reviewed_at is required")
    if not rationale:
        raise ValueError("rationale is required")
    if not (review_item_ids or source_table or derived_class):
        raise ValueError("at least one filter is required")


def _matches(
    row: dict[str, str],
    *,
    review_item_ids: set[str] | None,
    source_table: str | None,
    derived_class: str | None,
) -> bool:
    if review_item_ids is not None and _clean(row.get("review_item_id")) not in review_item_ids:
        return False
    if source_table is not None and _clean(row.get("source_table")) != source_table:
        return False
    if derived_class is not None and _clean(row.get("derived_class")) != derived_class:
        return False
    return True


def fill_governance_decision_csv(
    *,
    csv_path: Path,
    decision: str,
    reviewer: str,
    reviewed_at: str,
    rationale: str,
    review_item_ids: list[str] | None = None,
    source_table: str | None = None,
    derived_class: str | None = None,
    output_path: Path | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    reviewer = _clean(reviewer)
    reviewed_at = _clean(reviewed_at)
    rationale = _clean(rationale)
    source_table = _clean(source_table) or None
    derived_class = _clean(derived_class) or None
    cleaned_ids = [_clean(item) for item in review_item_ids or [] if _clean(item)]
    review_id_filter = set(cleaned_ids) if cleaned_ids else None
    _validate_inputs(
        decision=decision,
        reviewer=reviewer,
        reviewed_at=reviewed_at,
        rationale=rationale,
        review_item_ids=cleaned_ids,
        source_table=source_table,
        derived_class=derived_class,
    )

    fieldnames, rows = _read_csv(csv_path)
    target_path = output_path or csv_path
    matched_ids = []
    updated_ids = []
    skipped_existing = 0

    for row in rows:
        if not _matches(
            row,
            review_item_ids=review_id_filter,
            source_table=source_table,
            derived_class=derived_class,
        ):
            continue
        review_item_id = _clean(row.get("review_item_id"))
        matched_ids.append(review_item_id)
        if _clean(row.get("decision")) and not overwrite:
            skipped_existing += 1
            continue
        row["decision"] = decision
        row["reviewer"] = reviewer
        row["reviewed_at"] = reviewed_at
        row["rationale"] = rationale
        updated_ids.append(review_item_id)

    _write_csv(target_path, fieldnames, rows)
    return {
        "fill_version": FILL_VERSION,
        "pipeline": "governance_decision_csv_fill",
        "generated_at": _utc_now(),
        "source_artifacts": {
            "input_csv": str(csv_path),
            "output_csv": str(target_path),
        },
        "filters": {
            "review_item_ids": cleaned_ids,
            "source_table": source_table,
            "derived_class": derived_class,
            "overwrite": overwrite,
        },
        "summary": {
            "total_rows": len(rows),
            "matched_rows": len(matched_ids),
            "updated_rows": len(updated_ids),
            "skipped_existing_decisions": skipped_existing,
            "writes_to_database": False,
            "creates_real_governance_issues": False,
        },
        "updated_review_item_ids": updated_ids,
        "skipped_existing_review_item_ids": [
            item for item in matched_ids if item not in updated_ids
        ],
        "boundaries": {
            "offline_only": True,
            "writes_to_database": False,
            "creates_real_governance_issues": False,
            "applies_model_changes": False,
            "publishes_model_package": False,
            "executes_runtime_query": False,
            "auto_accepts_candidates": False,
            "requires_explicit_human_decision": True,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fill selected governance review decision CSV rows",
    )
    parser.add_argument("--csv", type=Path, required=True, help="Decision CSV path")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional output CSV path. Defaults to updating --csv in place.",
    )
    parser.add_argument(
        "--review-item-id",
        action="append",
        dest="review_item_ids",
        default=None,
        help="Review item id to fill. Can be repeated.",
    )
    parser.add_argument("--source-table", default=None, help="Source table filter")
    parser.add_argument("--derived-class", default=None, help="Derived class filter")
    parser.add_argument(
        "--decision",
        required=True,
        choices=sorted(DECISION_OPTIONS),
        help="Explicit human decision to write",
    )
    parser.add_argument("--reviewer", required=True, help="Reviewer identifier")
    parser.add_argument("--reviewed-at", required=True, help="Review timestamp")
    parser.add_argument("--rationale", required=True, help="Human review rationale")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite rows that already contain a decision",
    )
    args = parser.parse_args()

    try:
        result = fill_governance_decision_csv(
            csv_path=args.csv,
            output_path=args.output,
            review_item_ids=args.review_item_ids,
            source_table=args.source_table,
            derived_class=args.derived_class,
            decision=args.decision,
            reviewer=args.reviewer,
            reviewed_at=args.reviewed_at,
            rationale=args.rationale,
            overwrite=args.overwrite,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    summary = result["summary"]
    print("=== Governance Decision CSV Fill ===\n")
    print(f"CSV: {args.csv}")
    print(f"Matched rows: {summary['matched_rows']}")
    print(f"Updated rows: {summary['updated_rows']}")
    print(f"Skipped existing decisions: {summary['skipped_existing_decisions']}")
    print(f"Output CSV: {result['source_artifacts']['output_csv']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
