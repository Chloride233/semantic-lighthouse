"""Precheck offline governance review decisions before applying them.

This script validates a human-authored governance_review_decisions.json against
governance_review_workspace.json and writes a report. It does not apply
decisions, write accepted changes, write to the database, or create governance
issues.

Usage:
  .venv/Scripts/python scripts/precheck_governance_review_decisions.py \
      --data-pack .tmp/adventureworks-semantic
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PRECHECK_VERSION = "1.0"
DECISION_OPTIONS = {"accept", "reject", "defer", "needs_more_evidence"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path, label: str | None = None) -> dict[str, Any]:
    if not path.is_file():
        name = label or path.name
        raise FileNotFoundError(f"{name} not found at {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _finding(
    *,
    severity: str,
    code: str,
    message: str,
    review_item_id: str | None = None,
) -> dict[str, str]:
    item = {
        "severity": severity,
        "code": code,
    }
    if review_item_id is not None:
        item["review_item_id"] = review_item_id
    item["message"] = message
    return item


def _decision_counts(decisions: list[dict[str, Any]], decision: str) -> int:
    return sum(1 for item in decisions if item.get("decision") == decision)


def _validate_decision(
    decision: dict[str, Any],
    valid_ids: set[str],
    seen_ids: set[str],
) -> list[dict[str, str]]:
    review_item_id = decision.get("review_item_id")
    review_item_id_str = str(review_item_id)
    decision_value = decision.get("decision")
    findings: list[dict[str, str]] = []

    if review_item_id_str not in valid_ids:
        findings.append(
            _finding(
                severity="ERROR",
                code="unknown_review_item_id",
                review_item_id=review_item_id_str,
                message=f"unknown review_item_id: {review_item_id_str}",
            )
        )
    if review_item_id_str in seen_ids:
        findings.append(
            _finding(
                severity="ERROR",
                code="duplicate_review_item_id",
                review_item_id=review_item_id_str,
                message=f"duplicate review_item_id: {review_item_id_str}",
            )
        )
    seen_ids.add(review_item_id_str)

    if decision_value not in DECISION_OPTIONS:
        findings.append(
            _finding(
                severity="ERROR",
                code="invalid_decision",
                review_item_id=review_item_id_str,
                message=(
                    f"invalid decision for {review_item_id_str}: "
                    f"{decision_value}"
                ),
            )
        )
    if decision_value == "accept" and not decision.get("rationale"):
        findings.append(
            _finding(
                severity="ERROR",
                code="accept_requires_rationale",
                review_item_id=review_item_id_str,
                message=(
                    f"accept decision requires rationale: {review_item_id_str}"
                ),
            )
        )
    if not decision.get("reviewer"):
        findings.append(
            _finding(
                severity="ERROR",
                code="missing_reviewer",
                review_item_id=review_item_id_str,
                message=f"decision requires reviewer: {review_item_id_str}",
            )
        )
    if not decision.get("reviewed_at"):
        findings.append(
            _finding(
                severity="ERROR",
                code="missing_reviewed_at",
                review_item_id=review_item_id_str,
                message=f"decision requires reviewed_at: {review_item_id_str}",
            )
        )
    return findings


def _findings(
    workspace: dict[str, Any],
    decisions: dict[str, Any],
) -> list[dict[str, str]]:
    valid_ids = {
        str(item.get("review_item_id"))
        for item in workspace.get("review_items", [])
    }
    seen_ids: set[str] = set()
    findings: list[dict[str, str]] = []
    for decision in decisions.get("decisions", []):
        findings.extend(_validate_decision(decision, valid_ids, seen_ids))

    undecided = len(valid_ids - seen_ids)
    if undecided:
        findings.append(
            _finding(
                severity="WARN",
                code="undecided_items",
                message=f"{undecided} workspace item(s) have no submitted decision.",
            )
        )
    return findings


def precheck_governance_review_decisions(
    data_dir: Path,
    decisions_path: Path | None = None,
) -> dict[str, Any]:
    workspace_path = data_dir / "governance_review_workspace.json"
    decisions_input = decisions_path or (data_dir / "governance_review_decisions.json")
    workspace = _read_json(workspace_path, "governance_review_workspace.json")
    decisions = _read_json(decisions_input, decisions_input.name)

    submitted = decisions.get("decisions", [])
    findings = _findings(workspace, decisions)
    error_count = sum(1 for item in findings if item["severity"] == "ERROR")
    warning_count = sum(1 for item in findings if item["severity"] == "WARN")
    workspace_items = len(workspace.get("review_items", []))
    undecided_items = max(0, workspace_items - len({
        decision.get("review_item_id") for decision in submitted
    }))

    if error_count:
        status = "FAIL"
    elif warning_count:
        status = "WARN"
    else:
        status = "PASS"

    return {
        "precheck_version": PRECHECK_VERSION,
        "pipeline": "governance_review_decision_precheck",
        "generated_at": _utc_now(),
        "data_pack": workspace.get("data_pack", {"path": str(data_dir)}),
        "source_artifacts": {
            "governance_review_workspace": str(workspace_path),
            "governance_review_decisions": str(decisions_input),
        },
        "summary": {
            "precheck_status": status,
            "workspace_items": workspace_items,
            "submitted_decisions": len(submitted),
            "accepted_decisions": _decision_counts(submitted, "accept"),
            "rejected_decisions": _decision_counts(submitted, "reject"),
            "deferred_decisions": _decision_counts(submitted, "defer"),
            "needs_more_evidence_decisions": _decision_counts(
                submitted,
                "needs_more_evidence",
            ),
            "undecided_items": undecided_items,
            "error_count": error_count,
            "warning_count": warning_count,
            "ready_for_apply": error_count == 0,
            "writes_to_database": False,
        },
        "findings": findings,
        "boundaries": {
            "offline_only": True,
            "writes_to_database": False,
            "creates_real_governance_issues": False,
            "applies_model_changes": False,
            "publishes_model_package": False,
            "hard_reasoning_allowed": False,
            "precheck_only": True,
        },
    }


def render_markdown(result: dict[str, Any]) -> str:
    summary = result["summary"]
    lines = [
        "# Governance Review Decision Precheck",
        "",
        f"- Generated at: `{result['generated_at']}`",
        f"- Data pack: `{result['data_pack']['path']}`",
        f"- Precheck status: `{summary['precheck_status']}`",
        f"- Ready for apply: `{str(summary['ready_for_apply']).lower()}`",
        f"- Errors: `{summary['error_count']}`",
        f"- Warnings: `{summary['warning_count']}`",
        "- Writes to database: `false`",
        "",
        "## Findings",
        "",
        "| Severity | Code | Review item | Message |",
        "|---|---|---|---|",
    ]
    for finding in result["findings"]:
        message = str(finding.get("message") or "").replace("|", "\\|")
        lines.append(
            "| "
            f"{finding.get('severity')} | "
            f"{finding.get('code')} | "
            f"{finding.get('review_item_id', '')} | "
            f"{message} |"
        )
    lines.extend(
        [
            "",
            "## Boundaries",
            "",
            "- Offline only: `true`",
            "- Writes to database: `false`",
            "- Applies model changes: `false`",
            "- Publishes model package: `false`",
            "- Precheck only: `true`",
            "",
        ]
    )
    return "\n".join(lines)


def write_decision_precheck(
    data_dir: Path,
    output_path: Path,
    markdown_output_path: Path | None,
    decisions_path: Path | None = None,
) -> dict[str, Any]:
    result = precheck_governance_review_decisions(data_dir, decisions_path)
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
        description="Precheck offline governance review decisions",
    )
    parser.add_argument(
        "--data-pack",
        type=Path,
        required=True,
        help="Data pack directory containing governance_review_workspace.json",
    )
    parser.add_argument(
        "--decisions",
        type=Path,
        default=None,
        help=(
            "Decision input path "
            "(default: <data-pack>/governance_review_decisions.json)"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=(
            "JSON output path "
            "(default: <data-pack>/governance_review_decisions_precheck.json)"
        ),
    )
    parser.add_argument(
        "--markdown-output",
        type=Path,
        default=None,
        help=(
            "Markdown output path "
            "(default: <data-pack>/governance_review_decisions_precheck.md)"
        ),
    )
    args = parser.parse_args()

    output = args.output or (
        args.data_pack / "governance_review_decisions_precheck.json"
    )
    markdown_output = (
        args.markdown_output
        if args.markdown_output is not None
        else args.data_pack / "governance_review_decisions_precheck.md"
    )

    try:
        result = write_decision_precheck(
            args.data_pack,
            output,
            markdown_output,
            args.decisions,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    summary = result["summary"]
    print("=== Governance Review Decision Precheck ===\n")
    print(f"Data pack: {args.data_pack}")
    print(f"Precheck status: {summary['precheck_status']}")
    print(f"Ready for apply: {summary['ready_for_apply']}")
    print(f"Errors: {summary['error_count']}")
    print(f"Warnings: {summary['warning_count']}")
    print(f"JSON: {output}")
    print(f"Markdown: {markdown_output}")
    return 1 if summary["precheck_status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
