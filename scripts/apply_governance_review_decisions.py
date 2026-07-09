"""Apply offline governance review decisions to produce accepted changes.

This script reads governance_review_workspace.json plus a human-authored
governance_review_decisions.json file. Accepted decisions are converted into
accepted_governance_changes.json for the next offline draft-building step.

It does not write to the database, create real governance issues, apply model
changes, publish model packages, or grant hard reasoning rights.

Usage:
  .venv/Scripts/python scripts/apply_governance_review_decisions.py \
      --data-pack .tmp/adventureworks-semantic
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CHANGE_VERSION = "1.0"
DECISION_OPTIONS = {"accept", "reject", "defer", "needs_more_evidence"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _artifact_path(data_dir: Path, filename: str) -> str | None:
    path = data_dir / filename
    if not path.is_file():
        return None
    return str(path)


def _load_workspace(data_dir: Path) -> dict[str, Any]:
    path = data_dir / "governance_review_workspace.json"
    if not path.is_file():
        raise FileNotFoundError(f"governance_review_workspace.json not found in {data_dir}")
    return _read_json(path)


def _load_decisions(data_dir: Path, decisions_path: Path | None = None) -> dict[str, Any]:
    path = decisions_path or (data_dir / "governance_review_decisions.json")
    if not path.is_file():
        raise FileNotFoundError(f"governance_review_decisions.json not found at {path}")
    return _read_json(path)


def _validate_decisions(
    workspace: dict[str, Any],
    decisions: dict[str, Any],
) -> None:
    valid_ids = {
        item.get("review_item_id")
        for item in workspace.get("review_items", [])
    }
    errors = []
    seen_ids = set()
    for decision in decisions.get("decisions", []):
        review_item_id = decision.get("review_item_id")
        decision_value = decision.get("decision")
        if review_item_id not in valid_ids:
            errors.append(f"unknown review_item_id: {review_item_id}")
        if review_item_id in seen_ids:
            errors.append(f"duplicate review_item_id: {review_item_id}")
        seen_ids.add(review_item_id)
        if decision_value not in DECISION_OPTIONS:
            errors.append(
                f"invalid decision for {review_item_id}: {decision_value}"
            )
        if decision_value == "accept" and not decision.get("rationale"):
            errors.append(f"accept decision requires rationale: {review_item_id}")
        if not decision.get("reviewer"):
            errors.append(f"decision requires reviewer: {review_item_id}")

    if errors:
        raise ValueError("; ".join(errors))


def _decision_record(decision: dict[str, Any]) -> dict[str, Any]:
    return {
        "decision": decision.get("decision"),
        "reviewer": decision.get("reviewer"),
        "reviewed_at": decision.get("reviewed_at"),
        "rationale": decision.get("rationale"),
    }


def _result_status(decision_value: str) -> str:
    if decision_value == "accept":
        return "accepted_for_draft"
    if decision_value == "reject":
        return "rejected"
    if decision_value == "defer":
        return "deferred"
    return "needs_more_evidence"


def _change_type(item: dict[str, Any]) -> str:
    scope = item.get("affected_scope", {})
    if scope.get("derived_class"):
        return "derived_class_candidate"
    return "governance_candidate"


def _accepted_change(
    item: dict[str, Any],
    decision: dict[str, Any],
) -> dict[str, Any]:
    review_item_id = item.get("review_item_id")
    scope = item.get("affected_scope", {})
    return {
        "change_id": f"accepted-{review_item_id}",
        "source_review_item_id": review_item_id,
        "status": "accepted_for_draft",
        "change_type": _change_type(item),
        "target": {
            "source_table": scope.get("source_table"),
            "derived_class": scope.get("derived_class"),
        },
        "finding": item.get("finding", {}),
        "evidence_anchors": item.get("evidence_anchors", []),
        "review": _decision_record(decision),
        "rollback_note": item.get("rollback_note"),
        "hard_reasoning_allowed": False,
    }


def _decision_result(
    item: dict[str, Any],
    decision: dict[str, Any],
) -> dict[str, Any]:
    decision_value = str(decision.get("decision"))
    return {
        "review_item_id": item.get("review_item_id"),
        "decision": decision_value,
        "result_status": _result_status(decision_value),
        "review": _decision_record(decision),
    }


def _count_decisions(decision_results: list[dict[str, Any]], decision: str) -> int:
    return sum(1 for item in decision_results if item.get("decision") == decision)


def apply_review_decisions(
    data_dir: Path,
    decisions_path: Path | None = None,
) -> dict[str, Any]:
    workspace = _load_workspace(data_dir)
    decisions = _load_decisions(data_dir, decisions_path)
    _validate_decisions(workspace, decisions)

    decisions_by_id = {
        decision.get("review_item_id"): decision
        for decision in decisions.get("decisions", [])
    }
    review_items_by_id = {
        item.get("review_item_id"): item
        for item in workspace.get("review_items", [])
    }

    decision_results = []
    accepted_changes = []
    for review_item_id, decision in decisions_by_id.items():
        item = review_items_by_id[review_item_id]
        decision_results.append(_decision_result(item, decision))
        if decision.get("decision") == "accept":
            accepted_changes.append(_accepted_change(item, decision))

    workspace_items = len(workspace.get("review_items", []))
    submitted_decisions = len(decision_results)
    return {
        "change_version": CHANGE_VERSION,
        "pipeline": "governance_review_decisions",
        "generated_at": _utc_now(),
        "data_pack": workspace.get("data_pack", {"path": str(data_dir)}),
        "source_artifacts": {
            "governance_review_workspace": str(
                data_dir / "governance_review_workspace.json"
            ),
            "governance_review_decisions": str(
                decisions_path or data_dir / "governance_review_decisions.json"
            ),
            "adventureworks_ontology_seed": _artifact_path(
                data_dir,
                "adventureworks_ontology_seed.json",
            ),
        },
        "summary": {
            "workspace_items": workspace_items,
            "submitted_decisions": submitted_decisions,
            "accepted_decisions": _count_decisions(decision_results, "accept"),
            "rejected_decisions": _count_decisions(decision_results, "reject"),
            "deferred_decisions": _count_decisions(decision_results, "defer"),
            "needs_more_evidence_decisions": _count_decisions(
                decision_results,
                "needs_more_evidence",
            ),
            "accepted_change_count": len(accepted_changes),
            "undecided_items": workspace_items - submitted_decisions,
        },
        "accepted_changes": accepted_changes,
        "decision_results": decision_results,
        "boundaries": {
            "offline_only": True,
            "writes_to_database": False,
            "creates_real_governance_issues": False,
            "applies_model_changes": False,
            "publishes_model_package": False,
            "hard_reasoning_allowed": False,
            "requires_human_review": True,
        },
    }


def render_markdown(result: dict[str, Any]) -> str:
    summary = result["summary"]
    lines = [
        "# Accepted Governance Changes",
        "",
        f"- Generated at: `{result['generated_at']}`",
        f"- Data pack: `{result['data_pack']['path']}`",
        f"- Submitted decisions: `{summary['submitted_decisions']}`",
        f"- Accepted changes: `{summary['accepted_change_count']}`",
        f"- Undecided items: `{summary['undecided_items']}`",
        "- Hard reasoning allowed: `false`",
        "",
        "## Accepted Changes",
        "",
        "| Change | Review item | Type | Table | Derived class | Reviewer |",
        "|---|---|---|---|---|---|",
    ]
    for change in result["accepted_changes"]:
        target = change.get("target", {})
        review = change.get("review", {})
        lines.append(
            "| "
            f"{change.get('change_id')} | "
            f"{change.get('source_review_item_id')} | "
            f"{change.get('change_type')} | "
            f"{target.get('source_table')} | "
            f"{target.get('derived_class')} | "
            f"{review.get('reviewer')} |"
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
            "- Accepted changes are inputs for draft generation, not runtime facts.",
            "",
        ]
    )
    return "\n".join(lines)


def write_accepted_changes(
    data_dir: Path,
    output_path: Path,
    markdown_output_path: Path | None,
    decisions_path: Path | None = None,
) -> dict[str, Any]:
    result = apply_review_decisions(data_dir, decisions_path)
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
        description="Apply offline governance review decisions",
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
            "(default: <data-pack>/accepted_governance_changes.json)"
        ),
    )
    parser.add_argument(
        "--markdown-output",
        type=Path,
        default=None,
        help=(
            "Markdown output path "
            "(default: <data-pack>/accepted_governance_changes.md)"
        ),
    )
    args = parser.parse_args()

    output = args.output or (args.data_pack / "accepted_governance_changes.json")
    markdown_output = (
        args.markdown_output
        if args.markdown_output is not None
        else args.data_pack / "accepted_governance_changes.md"
    )

    try:
        result = write_accepted_changes(
            args.data_pack,
            output,
            markdown_output,
            args.decisions,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    summary = result["summary"]
    print("=== Governance Review Decisions ===\n")
    print(f"Data pack: {args.data_pack}")
    print(f"Submitted decisions: {summary['submitted_decisions']}")
    print(f"Accepted changes: {summary['accepted_change_count']}")
    print(f"Undecided items: {summary['undecided_items']}")
    print(f"JSON: {output}")
    print(f"Markdown: {markdown_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
