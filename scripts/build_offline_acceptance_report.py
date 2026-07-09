"""Build an offline semantic loop acceptance report.

This script summarizes the current end-to-end offline chain:

Semantic CI -> governance review -> accepted ontology -> model package
-> dataset binding -> runtime query dry run -> semantic asset feedback.

It reads existing artifacts only. It does not run child pipelines, write to the
database, create governance issues, publish packages, or execute runtime
queries.

Usage:
  .venv/Scripts/python scripts/build_offline_acceptance_report.py \
      --data-pack .tmp/adventureworks-semantic
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ACCEPTANCE_VERSION = "1.0"


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


def _sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _artifact(path: Path) -> dict[str, str | None]:
    return {
        "path": str(path),
        "sha256": _sha256(path),
    }


def _stage(stage: str, status: str, evidence: dict[str, Any]) -> dict[str, Any]:
    return {
        "stage": stage,
        "status": status,
        "evidence": evidence,
    }


def _criterion(criterion: str, status: str) -> dict[str, str]:
    return {
        "criterion": criterion,
        "status": status,
    }


def _semantic_ci_stage(semantic_ci: dict[str, Any]) -> dict[str, Any]:
    summary = semantic_ci.get("summary", {})
    return _stage(
        "semantic_ci",
        str(summary.get("gate_status")),
        {
            "hard_failures": int(summary.get("hard_failures", 0) or 0),
            "total_candidates": int(summary.get("total_candidates", 0) or 0),
            "critical_candidates": int(
                summary.get("critical_candidates", 0) or 0
            ),
        },
    )


def _effective_pending_review_items(
    workspace: dict[str, Any],
    changes: dict[str, Any],
) -> int:
    change_summary = changes.get("summary", {})
    if "undecided_items" in change_summary:
        return int(change_summary.get("undecided_items", 0) or 0)
    workspace_summary = workspace.get("summary", {})
    return int(workspace_summary.get("pending_review_items", 0) or 0)


def _effective_total_review_items(
    workspace: dict[str, Any],
    changes: dict[str, Any],
) -> int:
    change_summary = changes.get("summary", {})
    if "workspace_items" in change_summary:
        return int(change_summary.get("workspace_items", 0) or 0)
    workspace_summary = workspace.get("summary", {})
    return int(workspace_summary.get("total_review_items", 0) or 0)


def _governance_stage(
    workspace: dict[str, Any],
    changes: dict[str, Any],
) -> dict[str, Any]:
    pending = _effective_pending_review_items(workspace, changes)
    status = "PENDING_REVIEW" if pending else "REVIEW_COMPLETE"
    return _stage(
        "governance_review",
        status,
        {
            "total_review_items": _effective_total_review_items(
                workspace,
                changes,
            ),
            "pending_review_items": pending,
        },
    )


def _accepted_ontology_stage(
    changes: dict[str, Any],
    drafts: dict[str, Any],
) -> dict[str, Any]:
    change_summary = changes.get("summary", {})
    draft_summary = drafts.get("summary", {})
    accepted = int(change_summary.get("accepted_change_count", 0) or 0)
    drafts_count = int(draft_summary.get("draft_count", 0) or 0)
    status = "ACCEPTED_DRAFTS_READY" if drafts_count else "NO_ACCEPTED_CHANGES"
    return _stage(
        "accepted_ontology",
        status,
        {
            "accepted_change_count": accepted,
            "draft_count": drafts_count,
            "undecided_items": int(change_summary.get("undecided_items", 0) or 0),
        },
    )


def _package_stage(package: dict[str, Any]) -> dict[str, Any]:
    summary = package.get("summary", {})
    return _stage(
        "model_package",
        str(summary.get("package_status")),
        {
            "source_draft_count": int(summary.get("source_draft_count", 0) or 0),
            "derived_class_count": int(summary.get("derived_class_count", 0) or 0),
        },
    )


def _binding_stage(binding: dict[str, Any]) -> dict[str, Any]:
    summary = binding.get("summary", {})
    return _stage(
        "dataset_binding",
        str(summary.get("binding_status")),
        {
            "binding_count": int(summary.get("binding_count", 0) or 0),
            "runtime_query_ready": bool(
                summary.get("runtime_query_ready", False)
            ),
        },
    )


def _runtime_stage(query_plan: dict[str, Any]) -> dict[str, Any]:
    summary = query_plan.get("summary", {})
    return _stage(
        "runtime_query",
        str(summary.get("query_status")),
        {
            "query_plan_count": int(summary.get("query_plan_count", 0) or 0),
            "executes_runtime_query": bool(
                summary.get("executes_runtime_query", False)
            ),
        },
    )


def _feedback_stage(feedback: dict[str, Any]) -> dict[str, Any]:
    summary = feedback.get("summary", {})
    return _stage(
        "semantic_asset_feedback",
        str(summary.get("feedback_status")),
        {
            "feedback_items": int(summary.get("total_feedback_items", 0) or 0),
            "requires_human_review": bool(
                summary.get("requires_human_review", False)
            ),
        },
    )


def _chain_status(summary: dict[str, Any]) -> str:
    if summary["pending_review_items"] > 0:
        return "BLOCKED_BY_HUMAN_REVIEW"
    if summary["query_status"] == "QUERY_PLANNED":
        return "READY_FOR_SAFETY_LANE"
    if summary["feedback_items"] > 0:
        return "BACKLOG_OPEN"
    return "OFFLINE_ACCEPTED"


def _acceptance_criteria(summary: dict[str, Any]) -> list[dict[str, str]]:
    semantic_ci_ok = (
        summary["semantic_ci_status"] in {"PASS", "WARN"}
        and summary.get("semantic_ci_hard_failures", 0) == 0
    )
    review_done = summary["pending_review_items"] == 0
    drafts_ready = summary["draft_count"] > 0
    package_bound = (
        summary["package_status"] == "BUILT"
        and summary["binding_status"] == "BOUND"
    )
    query_planned = summary["query_status"] == "QUERY_PLANNED"
    feedback_ready = summary["feedback_status"] in {
        "BACKLOG_OPEN",
        "NO_OPEN_FEEDBACK",
    }
    return [
        _criterion(
            "Semantic CI completed without hard failures",
            "PASS" if semantic_ci_ok else "FAIL",
        ),
        _criterion(
            "Governance candidates have human decisions",
            "PASS" if review_done else "BLOCKED",
        ),
        _criterion(
            "Accepted ontology drafts exist",
            "PASS" if drafts_ready else "BLOCKED",
        ),
        _criterion(
            "Offline package and dataset binding are ready",
            "PASS" if package_bound else "BLOCKED",
        ),
        _criterion(
            "Runtime query is ready for Safety Lane promotion",
            "PASS" if query_planned else "BLOCKED",
        ),
        _criterion(
            "Semantic asset feedback backlog is generated",
            "PASS" if feedback_ready else "FAIL",
        ),
    ]


def _summary(
    *,
    semantic_ci: dict[str, Any],
    workspace: dict[str, Any],
    changes: dict[str, Any],
    drafts: dict[str, Any],
    package: dict[str, Any],
    binding: dict[str, Any],
    query_plan: dict[str, Any],
    feedback: dict[str, Any],
) -> dict[str, Any]:
    semantic_summary = semantic_ci.get("summary", {})
    data_pack = semantic_ci.get("data_pack", feedback.get("data_pack", {}))
    change_summary = changes.get("summary", {})
    draft_summary = drafts.get("summary", {})
    package_summary = package.get("summary", {})
    binding_summary = binding.get("summary", {})
    query_summary = query_plan.get("summary", {})
    feedback_summary = feedback.get("summary", {})

    summary = {
        "chain_status": "UNKNOWN",
        "table_count": int(data_pack.get("table_count", 0) or 0),
        "total_rows": int(data_pack.get("total_rows", 0) or 0),
        "semantic_ci_status": semantic_summary.get("gate_status"),
        "governance_candidates": int(
            semantic_summary.get("total_candidates", 0) or 0
        ),
        "pending_review_items": _effective_pending_review_items(
            workspace,
            changes,
        ),
        "accepted_change_count": int(
            change_summary.get("accepted_change_count", 0) or 0
        ),
        "draft_count": int(draft_summary.get("draft_count", 0) or 0),
        "package_status": package_summary.get("package_status"),
        "binding_status": binding_summary.get("binding_status"),
        "query_status": query_summary.get("query_status"),
        "feedback_status": feedback_summary.get("feedback_status"),
        "feedback_items": int(
            feedback_summary.get("total_feedback_items", 0) or 0
        ),
        "ready_for_db_backed_runtime": False,
        "requires_human_review": bool(
            feedback_summary.get("requires_human_review", False)
            or _effective_pending_review_items(workspace, changes) > 0
        ),
    }
    summary["semantic_ci_hard_failures"] = int(
        semantic_summary.get("hard_failures", 0) or 0
    )
    summary["chain_status"] = _chain_status(summary)
    public_summary = dict(summary)
    public_summary.pop("semantic_ci_hard_failures")
    return public_summary


def build_offline_acceptance_report(data_dir: Path) -> dict[str, Any]:
    feedback = _read_json(
        data_dir / "semantic_asset_feedback.json",
        "semantic_asset_feedback.json",
    )
    semantic_ci = _read_json(
        data_dir / "semantic_ci_report.json",
        "semantic_ci_report.json",
    )
    workspace = _read_json(
        data_dir / "governance_review_workspace.json",
        "governance_review_workspace.json",
    )
    changes = _read_json(
        data_dir / "accepted_governance_changes.json",
        "accepted_governance_changes.json",
    )
    drafts = _read_json(
        data_dir / "accepted_ontology_drafts.json",
        "accepted_ontology_drafts.json",
    )
    package = _read_json(
        data_dir / "offline_model_package.json",
        "offline_model_package.json",
    )
    binding = _read_json(
        data_dir / "offline_dataset_binding.json",
        "offline_dataset_binding.json",
    )
    query_plan = _read_json(
        data_dir / "offline_runtime_query_plan.json",
        "offline_runtime_query_plan.json",
    )

    summary = _summary(
        semantic_ci=semantic_ci,
        workspace=workspace,
        changes=changes,
        drafts=drafts,
        package=package,
        binding=binding,
        query_plan=query_plan,
        feedback=feedback,
    )
    criteria_summary = dict(summary)
    criteria_summary["semantic_ci_hard_failures"] = int(
        semantic_ci.get("summary", {}).get("hard_failures", 0) or 0
    )

    return {
        "acceptance_version": ACCEPTANCE_VERSION,
        "pipeline": "offline_semantic_loop_acceptance",
        "generated_at": _utc_now(),
        "data_pack": semantic_ci.get("data_pack", feedback.get("data_pack", {})),
        "summary": summary,
        "stages": [
            _semantic_ci_stage(semantic_ci),
            _governance_stage(workspace, changes),
            _accepted_ontology_stage(changes, drafts),
            _package_stage(package),
            _binding_stage(binding),
            _runtime_stage(query_plan),
            _feedback_stage(feedback),
        ],
        "acceptance_criteria": _acceptance_criteria(criteria_summary),
        "source_artifacts": {
            "semantic_ci_report": _artifact(data_dir / "semantic_ci_report.json"),
            "governance_review_workspace": _artifact(
                data_dir / "governance_review_workspace.json"
            ),
            "accepted_governance_changes": _artifact(
                data_dir / "accepted_governance_changes.json"
            ),
            "accepted_ontology_drafts": _artifact(
                data_dir / "accepted_ontology_drafts.json"
            ),
            "offline_model_package": _artifact(
                data_dir / "offline_model_package.json"
            ),
            "offline_dataset_binding": _artifact(
                data_dir / "offline_dataset_binding.json"
            ),
            "offline_runtime_query_plan": _artifact(
                data_dir / "offline_runtime_query_plan.json"
            ),
            "semantic_asset_feedback": _artifact(
                data_dir / "semantic_asset_feedback.json"
            ),
        },
        "boundaries": {
            "offline_only": True,
            "writes_to_database": False,
            "creates_real_governance_issues": False,
            "applies_model_changes": False,
            "publishes_model_package": False,
            "activates_runtime": False,
            "executes_runtime_query": False,
            "requires_safety_lane_for_runtime": True,
        },
    }


def render_markdown(result: dict[str, Any]) -> str:
    summary = result["summary"]
    lines = [
        "# Offline Semantic Loop Acceptance Report",
        "",
        f"- Generated at: `{result['generated_at']}`",
        f"- Data pack: `{result['data_pack']['path']}`",
        f"- Chain status: `{summary['chain_status']}`",
        f"- Tables: `{summary['table_count']}`",
        f"- Rows: `{summary['total_rows']}`",
        f"- Pending review items: `{summary['pending_review_items']}`",
        f"- Feedback items: `{summary['feedback_items']}`",
        "- Writes to database: `false`",
        "",
        "## Stages",
        "",
        "| Stage | Status | Evidence |",
        "|---|---|---|",
    ]
    for stage in result["stages"]:
        evidence = json.dumps(stage["evidence"], ensure_ascii=False, sort_keys=True)
        lines.append(
            "| "
            f"{stage['stage']} | "
            f"{stage['status']} | "
            f"`{evidence}` |"
        )
    lines.extend(
        [
            "",
            "## Acceptance Criteria",
            "",
            "| Criterion | Status |",
            "|---|---|",
        ]
    )
    for criterion in result["acceptance_criteria"]:
        lines.append(
            "| "
            f"{criterion['criterion']} | "
            f"{criterion['status']} |"
        )
    lines.extend(
        [
            "",
            "## Boundaries",
            "",
            "- Offline only: `true`",
            "- Writes to database: `false`",
            "- Creates real governance issues: `false`",
            "- Publishes model package: `false`",
            "- Executes runtime query: `false`",
            "- DB-backed runtime promotion requires a separate Safety Lane.",
            "",
        ]
    )
    return "\n".join(lines)


def write_offline_acceptance_report(
    data_dir: Path,
    output_path: Path,
    markdown_output_path: Path | None,
) -> dict[str, Any]:
    result = build_offline_acceptance_report(data_dir)
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
        description="Build offline semantic loop acceptance report",
    )
    parser.add_argument(
        "--data-pack",
        type=Path,
        required=True,
        help="Data pack directory containing semantic_asset_feedback.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=(
            "JSON output path "
            "(default: <data-pack>/offline_acceptance_report.json)"
        ),
    )
    parser.add_argument(
        "--markdown-output",
        type=Path,
        default=None,
        help=(
            "Markdown output path "
            "(default: <data-pack>/offline_acceptance_report.md)"
        ),
    )
    args = parser.parse_args()

    output = args.output or (args.data_pack / "offline_acceptance_report.json")
    markdown_output = (
        args.markdown_output
        if args.markdown_output is not None
        else args.data_pack / "offline_acceptance_report.md"
    )

    try:
        result = write_offline_acceptance_report(
            args.data_pack,
            output,
            markdown_output,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    summary = result["summary"]
    print("=== Offline Semantic Loop Acceptance Report ===\n")
    print(f"Data pack: {args.data_pack}")
    print(f"Chain status: {summary['chain_status']}")
    print(f"Semantic CI: {summary['semantic_ci_status']}")
    print(f"Pending review items: {summary['pending_review_items']}")
    print(f"Runtime query: {summary['query_status']}")
    print(f"Feedback items: {summary['feedback_items']}")
    print(f"JSON: {output}")
    print(f"Markdown: {markdown_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
