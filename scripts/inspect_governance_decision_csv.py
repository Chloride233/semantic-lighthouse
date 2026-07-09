"""Inspect governance review decision CSV completion.

This script is a pre-flight helper for human review. It reads a filled or
partially filled governance_review_decisions_template.csv and reports whether
it is ready for run_post_review_semantic_loop.py. It does not convert, apply,
write to the database, create governance issues, or execute runtime queries.

Usage:
  .venv/Scripts/python scripts/inspect_governance_decision_csv.py \
      --csv .tmp/adventureworks-semantic/governance_review_decisions_template.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


INSPECTION_VERSION = "1.0"
REQUIRED_WHEN_DECIDED = ["reviewer", "reviewed_at", "rationale"]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: str | None) -> str:
    return (value or "").strip()


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _finding(
    *,
    code: str,
    row_number: int,
    review_item_id: str,
    message: str,
) -> dict[str, Any]:
    return {
        "severity": "ERROR",
        "code": code,
        "row_number": row_number,
        "review_item_id": review_item_id,
        "message": message,
    }


def _row_findings(row: dict[str, str], row_number: int) -> list[dict[str, Any]]:
    review_item_id = _clean(row.get("review_item_id"))
    decision = _clean(row.get("decision"))
    if not decision:
        return [
            _finding(
                code="blank_decision",
                row_number=row_number,
                review_item_id=review_item_id,
                message="decision is required before post-review runner.",
            )
        ]

    findings = []
    for field in REQUIRED_WHEN_DECIDED:
        if _clean(row.get(field)):
            continue
        findings.append(
            _finding(
                code=f"missing_{field}",
                row_number=row_number,
                review_item_id=review_item_id,
                message=f"{field} is required when decision is set.",
            )
        )
    return findings


def _read_csv(csv_path: Path) -> list[dict[str, str]]:
    if not csv_path.is_file():
        raise FileNotFoundError(f"{csv_path.name} not found at {csv_path}")
    with csv_path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def inspect_governance_decision_csv(csv_path: Path) -> dict[str, Any]:
    rows = _read_csv(csv_path)
    findings = []
    complete_rows = 0
    blank_decision_rows = 0
    incomplete_rows = 0

    for index, row in enumerate(rows, start=2):
        row_findings = _row_findings(row, index)
        findings.extend(row_findings)
        if not _clean(row.get("decision")):
            blank_decision_rows += 1
        elif row_findings:
            incomplete_rows += 1
        else:
            complete_rows += 1

    ready = not findings
    return {
        "inspection_version": INSPECTION_VERSION,
        "pipeline": "governance_decision_csv_inspection",
        "generated_at": _utc_now(),
        "source_artifacts": {
            "governance_review_decisions_csv": str(csv_path),
        },
        "summary": {
            "inspection_status": "PASS" if ready else "REVIEW_INCOMPLETE",
            "total_rows": len(rows),
            "complete_rows": complete_rows,
            "blank_decision_rows": blank_decision_rows,
            "incomplete_rows": incomplete_rows,
            "error_count": len(findings),
            "ready_for_post_review_runner": ready,
        },
        "findings": findings,
        "boundaries": {
            "offline_only": True,
            "writes_to_database": False,
            "creates_real_governance_issues": False,
            "applies_model_changes": False,
            "publishes_model_package": False,
            "executes_runtime_query": False,
            "inspection_only": True,
        },
    }


def render_markdown(result: dict[str, Any]) -> str:
    summary = result["summary"]
    lines = [
        "# Governance Decision CSV Inspection",
        "",
        f"- Generated at: `{result['generated_at']}`",
        f"- CSV: `{result['source_artifacts']['governance_review_decisions_csv']}`",
        f"- Inspection status: `{summary['inspection_status']}`",
        f"- Total rows: `{summary['total_rows']}`",
        f"- Complete rows: `{summary['complete_rows']}`",
        f"- Blank decision rows: `{summary['blank_decision_rows']}`",
        f"- Incomplete rows: `{summary['incomplete_rows']}`",
        f"- Ready for post-review runner: `{str(summary['ready_for_post_review_runner']).lower()}`",
        "",
        "## Findings",
        "",
        "| Severity | Code | Row | Review item | Message |",
        "|---|---|---|---|---|",
    ]
    for finding in result["findings"]:
        message = str(finding.get("message") or "").replace("|", "\\|")
        lines.append(
            "| "
            f"{finding.get('severity')} | "
            f"{finding.get('code')} | "
            f"{finding.get('row_number')} | "
            f"{finding.get('review_item_id')} | "
            f"{message} |"
        )
    lines.extend(
        [
            "",
            "## Boundaries",
            "",
            "- Offline only: `true`",
            "- Writes to database: `false`",
            "- Creates real governance issues: `false`",
            "- Applies model changes: `false`",
            "- Inspection only: `true`",
            "",
        ]
    )
    return "\n".join(lines)


def write_governance_decision_csv_inspection(
    csv_path: Path,
    output_path: Path,
    markdown_output_path: Path | None,
) -> dict[str, Any]:
    result = inspect_governance_decision_csv(csv_path)
    _write_json(output_path, result)
    if markdown_output_path is not None:
        markdown_output_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_output_path.write_text(
            render_markdown(result),
            encoding="utf-8",
        )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Inspect filled governance review decision CSV completion",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        required=True,
        help="Governance review decision CSV path",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=(
            "JSON output path "
            "(default: <csv parent>/governance_review_decisions_csv_inspection.json)"
        ),
    )
    parser.add_argument(
        "--markdown-output",
        type=Path,
        default=None,
        help=(
            "Markdown output path "
            "(default: <csv parent>/governance_review_decisions_csv_inspection.md)"
        ),
    )
    args = parser.parse_args()

    output = args.output or (
        args.csv.parent / "governance_review_decisions_csv_inspection.json"
    )
    markdown_output = (
        args.markdown_output
        if args.markdown_output is not None
        else args.csv.parent / "governance_review_decisions_csv_inspection.md"
    )
    try:
        result = write_governance_decision_csv_inspection(
            args.csv,
            output,
            markdown_output,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    summary = result["summary"]
    print("=== Governance Decision CSV Inspection ===\n")
    print(f"CSV: {args.csv}")
    print(f"Inspection status: {summary['inspection_status']}")
    print(f"Complete rows: {summary['complete_rows']}")
    print(f"Blank decision rows: {summary['blank_decision_rows']}")
    print(f"Incomplete rows: {summary['incomplete_rows']}")
    print(f"Ready for post-review runner: {summary['ready_for_post_review_runner']}")
    print(f"JSON: {output}")
    print(f"Markdown: {markdown_output}")
    return 0 if summary["ready_for_post_review_runner"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
