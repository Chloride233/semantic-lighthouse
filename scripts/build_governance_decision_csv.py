"""Build a human-fillable CSV template for governance review decisions.

The CSV is an operator-friendly view over governance_review_workspace.json. It
does not apply decisions, write to the database, create governance issues, or
grant hard reasoning rights.

Usage:
  .venv/Scripts/python scripts/build_governance_decision_csv.py \
      --data-pack .tmp/adventureworks-semantic
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any


CSV_COLUMNS = [
    "review_item_id",
    "decision",
    "reviewer",
    "reviewed_at",
    "rationale",
    "recommended_decision",
    "review_owner_role",
    "severity",
    "source_table",
    "derived_class",
    "finding_id",
    "rule_id",
    "finding_message",
    "required_checks",
    "evidence_anchor",
]

SAFE_EVIDENCE_ANCHOR_KEYS = {
    "column",
    "derived_class",
    "finding_id",
    "row",
    "rule_id",
    "source",
    "table",
}


def _read_json(path: Path, label: str | None = None) -> dict[str, Any]:
    if not path.is_file():
        name = label or path.name
        raise FileNotFoundError(f"{name} not found in {path.parent}")
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_evidence_anchor(item: dict[str, Any]) -> str:
    anchors = item.get("evidence_anchors") or []
    if not anchors:
        return ""
    safe_anchor = {
        key: value
        for key, value in anchors[0].items()
        if key in SAFE_EVIDENCE_ANCHOR_KEYS
    }
    return json.dumps(safe_anchor, sort_keys=True)


def _csv_row(item: dict[str, Any]) -> dict[str, str]:
    candidate = item.get("candidate", {})
    scope = item.get("affected_scope", {})
    finding = item.get("finding", {})
    review_requirements = item.get("review_requirements", {})
    required_checks = review_requirements.get("required_checks") or []
    return {
        "review_item_id": str(item.get("review_item_id") or ""),
        "decision": "",
        "reviewer": "",
        "reviewed_at": "",
        "rationale": "",
        "recommended_decision": str(
            candidate.get("recommended_decision") or ""
        ),
        "review_owner_role": str(candidate.get("review_owner_role") or ""),
        "severity": str(candidate.get("severity") or ""),
        "source_table": str(scope.get("source_table") or ""),
        "derived_class": str(scope.get("derived_class") or ""),
        "finding_id": str(finding.get("finding_id") or ""),
        "rule_id": str(finding.get("rule_id") or ""),
        "finding_message": str(finding.get("message") or ""),
        "required_checks": ";".join(str(item) for item in required_checks),
        "evidence_anchor": _safe_evidence_anchor(item),
    }


def build_governance_decision_csv(data_dir: Path) -> list[dict[str, str]]:
    workspace = _read_json(
        data_dir / "governance_review_workspace.json",
        "governance_review_workspace.json",
    )
    return [_csv_row(item) for item in workspace.get("review_items", [])]


def write_governance_decision_csv(
    data_dir: Path,
    output_path: Path,
) -> list[dict[str, str]]:
    rows = build_governance_decision_csv(data_dir)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build offline governance review decision CSV template",
    )
    parser.add_argument(
        "--data-pack",
        type=Path,
        required=True,
        help="Data pack directory containing governance_review_workspace.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=(
            "CSV output path "
            "(default: <data-pack>/governance_review_decisions_template.csv)"
        ),
    )
    args = parser.parse_args()

    output = args.output or (
        args.data_pack / "governance_review_decisions_template.csv"
    )
    try:
        rows = write_governance_decision_csv(args.data_pack, output)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print("=== Governance Review Decision CSV Template ===\n")
    print(f"Data pack: {args.data_pack}")
    print(f"Template decisions: {len(rows)}")
    print("Ready for apply: False")
    print("Requires human review: True")
    print(f"CSV: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
