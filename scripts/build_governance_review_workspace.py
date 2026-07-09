"""Build an offline governance candidate review workspace.

The workspace turns governance_review_packet.json into decision-ready review
items with source row identity, affected scope, required checks, and an empty
decision record. It does not write to the database, create governance issues,
apply model changes, or publish a model package.

Usage:
  .venv/Scripts/python scripts/build_governance_review_workspace.py \
      --data-pack .tmp/adventureworks-semantic
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


WORKSPACE_VERSION = "1.0"
DECISION_OPTIONS = ["accept", "reject", "defer", "needs_more_evidence"]


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


def _derived_class_group_sizes(seed: dict[str, Any] | None) -> dict[tuple[str, str], int]:
    sizes: dict[tuple[str, str], int] = {}
    if not seed:
        return sizes

    for item in seed.get("derived_classes", []):
        derived_class = item.get("derived_class")
        source_table = item.get("source_table")
        if not derived_class or not source_table:
            continue
        sizes[(str(source_table), str(derived_class))] = len(
            item.get("candidate_ids", []),
        )
    return sizes


def _source_record_identity(anchor: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": anchor.get("source"),
        "table": anchor.get("table"),
        "row": anchor.get("row"),
        "finding_id": anchor.get("finding_id"),
        "rule_id": anchor.get("rule_id"),
    }


def _affected_scope(
    anchor: dict[str, Any],
    group_sizes: dict[tuple[str, str], int],
) -> dict[str, Any]:
    source_table = anchor.get("table")
    derived_class = anchor.get("derived_class")
    size = 1
    if source_table and derived_class:
        size = group_sizes.get((str(source_table), str(derived_class)), 1)
    return {
        "source_table": source_table,
        "derived_class": derived_class,
        "candidate_group_size": size,
    }


def _decision_record() -> dict[str, Any]:
    return {
        "status": "pending",
        "allowed_decisions": DECISION_OPTIONS,
        "decision": None,
        "reviewer": None,
        "reviewed_at": None,
        "rationale": None,
    }


def _review_item(
    item: dict[str, Any],
    group_sizes: dict[tuple[str, str], int],
) -> dict[str, Any]:
    anchor = _safe_anchor(item.get("evidence_anchor", {}) or {})
    return {
        "review_item_id": item.get("candidate_id"),
        "candidate": {
            "candidate_id": item.get("candidate_id"),
            "status": item.get("status", "open"),
            "severity": item.get("severity", "info"),
            "candidate_types": item.get("candidate_types", []),
            "recommended_decision": item.get("recommended_decision"),
            "review_owner_role": item.get("review_owner_role"),
        },
        "source_record_identity": _source_record_identity(anchor),
        "finding": item.get("finding", {}),
        "suggested_action": item.get("suggested_action"),
        "affected_scope": _affected_scope(anchor, group_sizes),
        "review_requirements": {
            "requires_human_review": True,
            "required_checks": item.get("required_checks", []),
        },
        "rollback_note": item.get("rollback_note"),
        "evidence_anchors": [anchor],
        "decision_record": _decision_record(),
        "safety": {
            "applies_model_change": False,
            "creates_real_governance_issue": False,
            "publishes_model_package": False,
        },
    }


def _count_by(items: list[dict[str, Any]], getter_name: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        if getter_name == "owner":
            value = item["candidate"].get("review_owner_role")
        elif getter_name == "decision":
            value = item["candidate"].get("recommended_decision")
        else:
            value = item["affected_scope"].get("derived_class")
        key = str(value or "unknown")
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def build_review_workspace(data_dir: Path) -> dict[str, Any]:
    packet_path = data_dir / "governance_review_packet.json"
    if not packet_path.is_file():
        raise FileNotFoundError(f"governance_review_packet.json not found in {data_dir}")

    seed_path = data_dir / "adventureworks_ontology_seed.json"
    seed = _read_json(seed_path) if seed_path.is_file() else None
    packet = _read_json(packet_path)
    group_sizes = _derived_class_group_sizes(seed)
    review_items = [
        _review_item(item, group_sizes)
        for item in packet.get("review_items", [])
    ]
    requires_human_review = bool(
        packet.get("summary", {}).get("requires_human_review", bool(review_items))
    )

    return {
        "workspace_version": WORKSPACE_VERSION,
        "pipeline": "governance_candidate_review_workspace",
        "generated_at": _utc_now(),
        "data_pack": packet.get("data_pack", {"path": str(data_dir)}),
        "source_artifacts": {
            "governance_review_packet": str(packet_path),
            "adventureworks_ontology_seed": _artifact_path(
                data_dir,
                "adventureworks_ontology_seed.json",
            ),
            "semantic_ci_report": _artifact_path(
                data_dir,
                "semantic_ci_report.json",
            ),
        },
        "summary": {
            "total_review_items": len(review_items),
            "pending_review_items": len(review_items),
            "requires_human_review": requires_human_review,
            "by_owner_role": _count_by(review_items, "owner"),
            "by_recommended_decision": _count_by(review_items, "decision"),
            "by_derived_class": _count_by(review_items, "derived_class"),
        },
        "review_items": review_items,
        "boundaries": {
            "offline_only": True,
            "writes_to_database": False,
            "creates_real_governance_issues": False,
            "applies_model_changes": False,
            "publishes_model_package": False,
            "requires_human_review": requires_human_review,
        },
    }


def _markdown_table_rows(items: list[dict[str, Any]]) -> list[str]:
    rows = []
    for item in items:
        candidate = item["candidate"]
        scope = item["affected_scope"]
        finding = item.get("finding", {})
        message = str(finding.get("message") or "").replace("|", "\\|")
        rows.append(
            "| "
            f"{item.get('review_item_id')} | "
            f"{candidate.get('severity')} | "
            f"{candidate.get('review_owner_role')} | "
            f"{candidate.get('recommended_decision')} | "
            f"{scope.get('source_table')} | "
            f"{scope.get('derived_class')} | "
            f"{message} |"
        )
    return rows


def render_markdown(workspace: dict[str, Any]) -> str:
    summary = workspace["summary"]
    lines = [
        "# Governance Candidate Review Workspace",
        "",
        f"- Generated at: `{workspace['generated_at']}`",
        f"- Data pack: `{workspace['data_pack']['path']}`",
        f"- Review items: `{summary['total_review_items']}`",
        f"- Pending review items: `{summary['pending_review_items']}`",
        f"- Requires human review: `{summary['requires_human_review']}`",
        "- Status remains `pending` until a human reviewer records a decision.",
        "",
        "## Review Items",
        "",
        "| Item | Severity | Owner | Recommended decision | Table | Derived class | Finding |",
        "|---|---|---|---|---|---|---|",
    ]
    lines.extend(_markdown_table_rows(workspace["review_items"]))
    lines.extend(
        [
            "",
            "## Boundaries",
            "",
            "- Offline only: `true`",
            "- Writes to database: `false`",
            "- Creates real governance issues: `false`",
            "- Applies model changes: `false`",
            "- Publishes model package: `false`",
            "",
        ]
    )
    return "\n".join(lines)


def write_review_workspace(
    data_dir: Path,
    output_path: Path,
    markdown_output_path: Path | None,
) -> dict[str, Any]:
    workspace = build_review_workspace(data_dir)
    _write_json(output_path, workspace)
    if markdown_output_path is not None:
        markdown_output_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_output_path.write_text(
            render_markdown(workspace),
            encoding="utf-8",
        )
    return workspace


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build offline governance candidate review workspace",
    )
    parser.add_argument(
        "--data-pack",
        type=Path,
        required=True,
        help="Data pack directory containing governance_review_packet.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=(
            "JSON output path "
            "(default: <data-pack>/governance_review_workspace.json)"
        ),
    )
    parser.add_argument(
        "--markdown-output",
        type=Path,
        default=None,
        help=(
            "Markdown output path "
            "(default: <data-pack>/governance_review_workspace.md)"
        ),
    )
    args = parser.parse_args()

    output = args.output or (args.data_pack / "governance_review_workspace.json")
    markdown_output = (
        args.markdown_output
        if args.markdown_output is not None
        else args.data_pack / "governance_review_workspace.md"
    )

    try:
        workspace = write_review_workspace(args.data_pack, output, markdown_output)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    summary = workspace["summary"]
    print("=== Governance Candidate Review Workspace ===\n")
    print(f"Data pack: {args.data_pack}")
    print(f"Review items: {summary['total_review_items']}")
    print(f"Pending: {summary['pending_review_items']}")
    print(f"Requires human review: {summary['requires_human_review']}")
    print(f"JSON: {output}")
    print(f"Markdown: {markdown_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
