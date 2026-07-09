"""Build a human-fillable offline governance review decision template.

The template is intentionally not ready for apply: every decision field starts
as null and must be filled by a human reviewer before being copied to
governance_review_decisions.json.

Usage:
  .venv/Scripts/python scripts/build_governance_decision_template.py \
      --data-pack .tmp/adventureworks-semantic
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TEMPLATE_VERSION = "1.0"
DECISION_OPTIONS = [
    "accept",
    "reject",
    "defer",
    "needs_more_evidence",
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path, label: str | None = None) -> dict[str, Any]:
    if not path.is_file():
        name = label or path.name
        raise FileNotFoundError(f"{name} not found in {path.parent}")
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


def _candidate_summary(item: dict[str, Any]) -> dict[str, Any]:
    candidate = item.get("candidate", {})
    return {
        "severity": candidate.get("severity"),
        "candidate_types": candidate.get("candidate_types", []),
        "recommended_decision": candidate.get("recommended_decision"),
        "review_owner_role": candidate.get("review_owner_role"),
    }


def _template_decision(item: dict[str, Any]) -> dict[str, Any]:
    review_requirements = item.get("review_requirements", {})
    return {
        "review_item_id": item.get("review_item_id"),
        "template_status": "needs_human_input",
        "candidate": _candidate_summary(item),
        "affected_scope": item.get("affected_scope", {}),
        "finding": item.get("finding", {}),
        "required_checks": review_requirements.get("required_checks", []),
        "evidence_anchors": item.get("evidence_anchors", []),
        "decision": None,
        "reviewer": None,
        "reviewed_at": None,
        "rationale": None,
    }


def _instructions() -> dict[str, Any]:
    return {
        "target_decision_file": "governance_review_decisions.json",
        "copy_template_before_filling": True,
        "required_fields": [
            "review_item_id",
            "decision",
            "reviewer",
            "reviewed_at",
            "rationale",
        ],
        "allowed_decisions": DECISION_OPTIONS,
        "apply_command": (
            ".\\.venv\\Scripts\\python scripts\\apply_governance_review_decisions.py "
            "--data-pack <data-pack>"
        ),
    }


def build_governance_decision_template(data_dir: Path) -> dict[str, Any]:
    workspace = _read_json(
        data_dir / "governance_review_workspace.json",
        "governance_review_workspace.json",
    )
    decisions = [
        _template_decision(item)
        for item in workspace.get("review_items", [])
    ]

    return {
        "template_version": TEMPLATE_VERSION,
        "pipeline": "governance_review_decision_template",
        "generated_at": _utc_now(),
        "data_pack": workspace.get("data_pack", {"path": str(data_dir)}),
        "source_artifacts": {
            "governance_review_workspace": str(
                data_dir / "governance_review_workspace.json"
            ),
            "semantic_ci_report": _artifact_path(
                data_dir,
                "semantic_ci_report.json",
            ),
            "adventureworks_ontology_seed": _artifact_path(
                data_dir,
                "adventureworks_ontology_seed.json",
            ),
        },
        "summary": {
            "total_template_decisions": len(decisions),
            "open_decisions": len(decisions),
            "ready_for_apply": False,
            "requires_human_review": True,
            "writes_to_database": False,
            "creates_real_governance_issues": False,
        },
        "instructions": _instructions(),
        "decisions": decisions,
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


def render_markdown(result: dict[str, Any]) -> str:
    summary = result["summary"]
    lines = [
        "# Governance Review Decision Template",
        "",
        f"- Generated at: `{result['generated_at']}`",
        f"- Data pack: `{result['data_pack']['path']}`",
        f"- Template decisions: `{summary['total_template_decisions']}`",
        f"- Ready for apply: `{str(summary['ready_for_apply']).lower()}`",
        "- Fill `decision`, `reviewer`, `reviewed_at`, and `rationale` before applying.",
        "",
        "## Decisions",
        "",
        "| Review item | Owner | Recommended | Table | Derived class | Decision |",
        "|---|---|---|---|---|---|",
    ]
    for decision in result["decisions"]:
        candidate = decision.get("candidate", {})
        scope = decision.get("affected_scope", {})
        lines.append(
            "| "
            f"{decision.get('review_item_id')} | "
            f"{candidate.get('review_owner_role')} | "
            f"{candidate.get('recommended_decision')} | "
            f"{scope.get('source_table')} | "
            f"{scope.get('derived_class')} | "
            f"{decision.get('decision')} |"
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
            "- Publishes model package: `false`",
            "- Auto-accepts candidates: `false`",
            "",
        ]
    )
    return "\n".join(lines)


def write_governance_decision_template(
    data_dir: Path,
    output_path: Path,
    markdown_output_path: Path | None,
) -> dict[str, Any]:
    result = build_governance_decision_template(data_dir)
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
        description="Build offline governance review decision template",
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
            "JSON output path "
            "(default: <data-pack>/governance_review_decisions_template.json)"
        ),
    )
    parser.add_argument(
        "--markdown-output",
        type=Path,
        default=None,
        help=(
            "Markdown output path "
            "(default: <data-pack>/governance_review_decisions_template.md)"
        ),
    )
    args = parser.parse_args()

    output = args.output or (
        args.data_pack / "governance_review_decisions_template.json"
    )
    markdown_output = (
        args.markdown_output
        if args.markdown_output is not None
        else args.data_pack / "governance_review_decisions_template.md"
    )

    try:
        result = write_governance_decision_template(
            args.data_pack,
            output,
            markdown_output,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    summary = result["summary"]
    print("=== Governance Review Decision Template ===\n")
    print(f"Data pack: {args.data_pack}")
    print(f"Template decisions: {summary['total_template_decisions']}")
    print(f"Ready for apply: {summary['ready_for_apply']}")
    print(f"Requires human review: {summary['requires_human_review']}")
    print(f"JSON: {output}")
    print(f"Markdown: {markdown_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
