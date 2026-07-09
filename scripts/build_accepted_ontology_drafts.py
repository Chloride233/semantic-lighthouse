"""Build offline accepted ontology drafts from accepted governance changes.

This script converts accepted_governance_changes.json into
accepted_ontology_drafts.json for the next offline model-package bridge. It
does not write to the database, apply model changes, publish packages, or make
accepted drafts available for hard runtime reasoning.

Usage:
  .venv/Scripts/python scripts/build_accepted_ontology_drafts.py \
      --data-pack .tmp/adventureworks-semantic
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DRAFT_ARTIFACT_VERSION = "1.0"


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


def _load_accepted_changes(data_dir: Path) -> dict[str, Any]:
    path = data_dir / "accepted_governance_changes.json"
    if not path.is_file():
        raise FileNotFoundError(f"accepted_governance_changes.json not found in {data_dir}")
    return _read_json(path)


def _classification_rule(change: dict[str, Any]) -> dict[str, Any]:
    finding = change.get("finding", {}) or {}
    return {
        "rule_id": finding.get("rule_id"),
        "finding_id": finding.get("finding_id"),
        "message": finding.get("message"),
    }


def _description(source_table: str | None) -> str:
    table = source_table or "source table"
    return f"Accepted derived class candidate for {table}."


def _derived_class_draft(change: dict[str, Any]) -> dict[str, Any]:
    target = change.get("target", {}) or {}
    source_table = target.get("source_table")
    derived_class = target.get("derived_class")
    if not source_table or not derived_class:
        raise ValueError(
            f"accepted change {change.get('change_id')} missing derived class target"
        )

    return {
        "draft_id": f"offline-draft-{change.get('change_id')}",
        "draft_type": "derived_class",
        "status": "accepted",
        "name": derived_class,
        "description": _description(str(source_table)),
        "source_change_id": change.get("change_id"),
        "source_review_item_id": change.get("source_review_item_id"),
        "source_table": source_table,
        "payload": {
            "generator": "governance_review_decisions_v1",
            "generation_key": f"derived_class:{source_table}:{derived_class}",
            "source_table": source_table,
            "derived_class": derived_class,
            "classification_rule": _classification_rule(change),
            "hard_reasoning_allowed": False,
        },
        "evidence_refs": change.get("evidence_anchors", []),
        "review": change.get("review", {}),
        "rollback_note": change.get("rollback_note"),
        "hard_reasoning_allowed": False,
    }


def _draft_from_change(change: dict[str, Any]) -> dict[str, Any]:
    change_type = change.get("change_type")
    if change_type == "derived_class_candidate":
        return _derived_class_draft(change)
    raise ValueError(
        f"unsupported accepted change type for {change.get('change_id')}: {change_type}"
    )


def build_accepted_ontology_drafts(data_dir: Path) -> dict[str, Any]:
    changes_artifact = _load_accepted_changes(data_dir)
    accepted_changes = changes_artifact.get("accepted_changes", [])
    drafts = [_draft_from_change(change) for change in accepted_changes]
    derived_class_count = sum(
        1 for draft in drafts if draft.get("draft_type") == "derived_class"
    )

    return {
        "draft_artifact_version": DRAFT_ARTIFACT_VERSION,
        "pipeline": "accepted_ontology_drafts",
        "generated_at": _utc_now(),
        "data_pack": changes_artifact.get("data_pack", {"path": str(data_dir)}),
        "source_artifacts": {
            "accepted_governance_changes": str(
                data_dir / "accepted_governance_changes.json"
            ),
            "governance_review_decisions": _artifact_path(
                data_dir,
                "governance_review_decisions.json",
            ),
            "governance_review_workspace": _artifact_path(
                data_dir,
                "governance_review_workspace.json",
            ),
        },
        "summary": {
            "accepted_change_count": len(accepted_changes),
            "draft_count": len(drafts),
            "derived_class_draft_count": derived_class_count,
            "hard_reasoning_allowed": False,
            "publishes_model_package": False,
        },
        "drafts": drafts,
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
        "# Accepted Ontology Drafts",
        "",
        f"- Generated at: `{result['generated_at']}`",
        f"- Data pack: `{result['data_pack']['path']}`",
        f"- Accepted changes: `{summary['accepted_change_count']}`",
        f"- Drafts: `{summary['draft_count']}`",
        f"- Derived class drafts: `{summary['derived_class_draft_count']}`",
        "- Hard reasoning allowed: `false`",
        "- Publishes model package: `false`",
        "",
        "## Drafts",
        "",
        "| Draft | Type | Status | Name | Source table | Source change |",
        "|---|---|---|---|---|---|",
    ]
    for draft in result["drafts"]:
        lines.append(
            "| "
            f"{draft.get('draft_id')} | "
            f"{draft.get('draft_type')} | "
            f"{draft.get('status')} | "
            f"{draft.get('name')} | "
            f"{draft.get('source_table')} | "
            f"{draft.get('source_change_id')} |"
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
            "- Drafts are not runtime facts until a package bridge publishes them.",
            "",
        ]
    )
    return "\n".join(lines)


def write_accepted_ontology_drafts(
    data_dir: Path,
    output_path: Path,
    markdown_output_path: Path | None,
) -> dict[str, Any]:
    result = build_accepted_ontology_drafts(data_dir)
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
        description="Build offline accepted ontology drafts",
    )
    parser.add_argument(
        "--data-pack",
        type=Path,
        required=True,
        help="Data pack directory containing accepted_governance_changes.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=(
            "JSON output path "
            "(default: <data-pack>/accepted_ontology_drafts.json)"
        ),
    )
    parser.add_argument(
        "--markdown-output",
        type=Path,
        default=None,
        help=(
            "Markdown output path "
            "(default: <data-pack>/accepted_ontology_drafts.md)"
        ),
    )
    args = parser.parse_args()

    output = args.output or (args.data_pack / "accepted_ontology_drafts.json")
    markdown_output = (
        args.markdown_output
        if args.markdown_output is not None
        else args.data_pack / "accepted_ontology_drafts.md"
    )

    try:
        result = write_accepted_ontology_drafts(
            args.data_pack,
            output,
            markdown_output,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    summary = result["summary"]
    print("=== Accepted Ontology Drafts ===\n")
    print(f"Data pack: {args.data_pack}")
    print(f"Accepted changes: {summary['accepted_change_count']}")
    print(f"Drafts: {summary['draft_count']}")
    print(f"Derived class drafts: {summary['derived_class_draft_count']}")
    print(f"JSON: {output}")
    print(f"Markdown: {markdown_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
