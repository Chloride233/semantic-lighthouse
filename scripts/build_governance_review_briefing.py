"""Build an offline governance review briefing.

The briefing groups pending governance review items by source table and derived
class so reviewers can make explicit decisions in batches. It does not record
decisions, apply model changes, write to the database, create governance issues,
publish packages, or execute runtime queries.

Usage:
  .venv/Scripts/python scripts/build_governance_review_briefing.py \
      --data-pack .tmp/adventureworks-semantic
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BRIEFING_VERSION = "1.0"
DECISION_OPTIONS = ["accept", "reject", "defer", "needs_more_evidence"]
REQUIRED_DECISION_FIELDS = ["decision", "reviewer", "reviewed_at", "rationale"]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _read_decision_csv(csv_path: Path | None) -> dict[str, dict[str, str]]:
    if csv_path is None or not csv_path.is_file():
        return {}
    with csv_path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return {
        _clean(row.get("review_item_id")): row
        for row in rows
        if _clean(row.get("review_item_id"))
    }


def _decision_complete(row: dict[str, str] | None) -> bool:
    if row is None:
        return False
    return all(_clean(row.get(field)) for field in REQUIRED_DECISION_FIELDS)


def _safe_anchor(anchor: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": anchor.get("source"),
        "finding_id": anchor.get("finding_id"),
        "rule_id": anchor.get("rule_id"),
        "table": anchor.get("table"),
        "row": anchor.get("row"),
        "column": anchor.get("column"),
        "derived_class": anchor.get("derived_class"),
    }


def _item_anchor(item: dict[str, Any]) -> dict[str, Any]:
    anchors = item.get("evidence_anchors") or []
    if anchors:
        return _safe_anchor(anchors[0] or {})
    return {}


def _item_scope(item: dict[str, Any]) -> tuple[str, str]:
    scope = item.get("affected_scope") or {}
    source_table = _clean(scope.get("source_table"))
    derived_class = _clean(scope.get("derived_class"))
    return source_table or "unknown", derived_class or "unknown"


def _required_checks(items: list[dict[str, Any]]) -> list[str]:
    checks = set()
    for item in items:
        requirements = item.get("review_requirements") or {}
        checks.update(_clean(check) for check in requirements.get("required_checks", []))
    return sorted(check for check in checks if check)


def _finding_messages(items: list[dict[str, Any]]) -> list[str]:
    messages = []
    for item in items:
        message = _clean((item.get("finding") or {}).get("message"))
        if message and message not in messages:
            messages.append(message)
    return messages[:3]


def _review_item_ids(items: list[dict[str, Any]]) -> list[str]:
    return [_clean(item.get("review_item_id")) for item in items]


def _fill_command_template(
    *,
    csv_path: Path | None,
    source_table: str,
    derived_class: str,
) -> str:
    csv_display = str(csv_path) if csv_path is not None else "<decision-csv>"
    return (
        ".\\.venv\\Scripts\\python scripts\\fill_governance_decision_csv.py "
        f"--csv {csv_display} "
        f"--source-table {source_table} "
        f"--derived-class {derived_class} "
        "--decision <decision> "
        "--reviewer <reviewer> "
        "--reviewed-at <reviewed_at> "
        '--rationale "<rationale>"'
    )


def _review_group(
    *,
    source_table: str,
    derived_class: str,
    items: list[dict[str, Any]],
    decisions_by_id: dict[str, dict[str, str]],
    csv_path: Path | None,
) -> dict[str, Any]:
    complete_ids = []
    pending_ids = []
    for review_item_id in _review_item_ids(items):
        if _decision_complete(decisions_by_id.get(review_item_id)):
            complete_ids.append(review_item_id)
        else:
            pending_ids.append(review_item_id)

    return {
        "group_key": f"{source_table}::{derived_class}",
        "source_table": source_table,
        "derived_class": derived_class,
        "total_items": len(items),
        "pending_decision_items": len(pending_ids),
        "completed_decision_items": len(complete_ids),
        "review_item_ids": _review_item_ids(items),
        "pending_review_item_ids": pending_ids,
        "completed_review_item_ids": complete_ids,
        "owner_roles": sorted(
            {
                _clean((item.get("candidate") or {}).get("review_owner_role"))
                for item in items
                if _clean((item.get("candidate") or {}).get("review_owner_role"))
            }
        ),
        "recommended_decisions": sorted(
            {
                _clean((item.get("candidate") or {}).get("recommended_decision"))
                for item in items
                if _clean((item.get("candidate") or {}).get("recommended_decision"))
            }
        ),
        "required_checks": _required_checks(items),
        "finding_messages": _finding_messages(items),
        "evidence_samples": [_item_anchor(item) for item in items[:3]],
        "fill_command_template": _fill_command_template(
            csv_path=csv_path,
            source_table=source_table,
            derived_class=derived_class,
        ),
    }


def _group_items(items: list[dict[str, Any]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        groups[_item_scope(item)].append(item)
    return dict(sorted(groups.items()))


def build_governance_review_briefing(
    data_dir: Path,
    csv_path: Path | None = None,
) -> dict[str, Any]:
    workspace_path = data_dir / "governance_review_workspace.json"
    if not workspace_path.is_file():
        raise FileNotFoundError(f"governance_review_workspace.json not found in {data_dir}")
    if csv_path is None:
        default_csv = data_dir / "governance_review_decisions_template.csv"
        csv_path = default_csv if default_csv.is_file() else None

    workspace = _read_json(workspace_path)
    review_items = workspace.get("review_items", [])
    decisions_by_id = _read_decision_csv(csv_path)
    groups = [
        _review_group(
            source_table=source_table,
            derived_class=derived_class,
            items=items,
            decisions_by_id=decisions_by_id,
            csv_path=csv_path,
        )
        for (source_table, derived_class), items in _group_items(review_items).items()
    ]
    pending_count = sum(group["pending_decision_items"] for group in groups)
    completed_count = sum(group["completed_decision_items"] for group in groups)

    return {
        "briefing_version": BRIEFING_VERSION,
        "pipeline": "governance_review_briefing",
        "generated_at": _utc_now(),
        "data_pack": workspace.get("data_pack", {"path": str(data_dir)}),
        "source_artifacts": {
            "governance_review_workspace": str(workspace_path),
            "governance_review_decisions_csv": str(csv_path) if csv_path else None,
        },
        "summary": {
            "total_review_items": len(review_items),
            "group_count": len(groups),
            "pending_decision_items": pending_count,
            "completed_decision_items": completed_count,
            "requires_human_review": pending_count > 0,
        },
        "decision_options": DECISION_OPTIONS,
        "review_groups": groups,
        "boundaries": {
            "offline_only": True,
            "writes_to_database": False,
            "creates_real_governance_issues": False,
            "applies_model_changes": False,
            "publishes_model_package": False,
            "executes_runtime_query": False,
            "briefing_only": True,
            "auto_accepts_candidates": False,
            "requires_explicit_human_decision": True,
        },
    }


def render_markdown(result: dict[str, Any]) -> str:
    summary = result["summary"]
    lines = [
        "# Governance Review Briefing",
        "",
        f"- Generated at: `{result['generated_at']}`",
        f"- Data pack: `{result['data_pack']['path']}`",
        f"- Review items: `{summary['total_review_items']}`",
        f"- Groups: `{summary['group_count']}`",
        f"- Pending decisions: `{summary['pending_decision_items']}`",
        f"- Completed decisions: `{summary['completed_decision_items']}`",
        "- This briefing does not record decisions.",
        "",
        "## Review Groups",
        "",
        "| Table | Derived class | Total | Pending | Completed | Required checks |",
        "|---|---|---:|---:|---:|---|",
    ]
    for group in result["review_groups"]:
        required_checks = ";".join(group.get("required_checks", []))
        lines.append(
            "| "
            f"{group['source_table']} | "
            f"{group['derived_class']} | "
            f"{group['total_items']} | "
            f"{group['pending_decision_items']} | "
            f"{group['completed_decision_items']} | "
            f"{required_checks} |"
        )
    lines.extend(["", "## Fill Command Templates", ""])
    for group in result["review_groups"]:
        lines.extend(
            [
                f"### {group['source_table']} / {group['derived_class']}",
                "",
                "```powershell",
                group["fill_command_template"],
                "```",
                "",
            ]
        )
    lines.extend(
        [
            "## Boundaries",
            "",
            "- Offline only: `true`",
            "- Writes to database: `false`",
            "- Creates real governance issues: `false`",
            "- Applies model changes: `false`",
            "- Publishes model package: `false`",
            "- Executes runtime query: `false`",
            "- Auto accepts candidates: `false`",
            "",
        ]
    )
    return "\n".join(lines)


def write_governance_review_briefing(
    data_dir: Path,
    csv_path: Path | None,
    output_path: Path,
    markdown_output_path: Path | None,
) -> dict[str, Any]:
    result = build_governance_review_briefing(data_dir, csv_path)
    _write_json(output_path, result)
    if markdown_output_path is not None:
        markdown_output_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_output_path.write_text(render_markdown(result), encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build offline governance review briefing",
    )
    parser.add_argument(
        "--data-pack",
        type=Path,
        required=True,
        help="Data pack directory containing governance_review_workspace.json",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=None,
        help=(
            "Optional decision CSV path "
            "(default: <data-pack>/governance_review_decisions_template.csv if present)"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=(
            "JSON output path "
            "(default: <data-pack>/governance_review_briefing.json)"
        ),
    )
    parser.add_argument(
        "--markdown-output",
        type=Path,
        default=None,
        help=(
            "Markdown output path "
            "(default: <data-pack>/governance_review_briefing.md)"
        ),
    )
    args = parser.parse_args()

    output = args.output or (args.data_pack / "governance_review_briefing.json")
    markdown_output = (
        args.markdown_output
        if args.markdown_output is not None
        else args.data_pack / "governance_review_briefing.md"
    )
    try:
        result = write_governance_review_briefing(
            args.data_pack,
            args.csv,
            output,
            markdown_output,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    summary = result["summary"]
    print("=== Governance Review Briefing ===\n")
    print(f"Data pack: {args.data_pack}")
    print(f"Review items: {summary['total_review_items']}")
    print(f"Groups: {summary['group_count']}")
    print(f"Pending decisions: {summary['pending_decision_items']}")
    print(f"Completed decisions: {summary['completed_decision_items']}")
    print(f"JSON: {output}")
    print(f"Markdown: {markdown_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
