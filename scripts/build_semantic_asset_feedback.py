"""Build an offline semantic asset feedback backlog.

This script closes the offline loop by converting Semantic CI, review,
package, binding, and runtime dry-run state into reviewable semantic asset
feedback items. It does not write to the database, create governance issues,
apply model changes, publish packages, or execute runtime queries.

Usage:
  .venv/Scripts/python scripts/build_semantic_asset_feedback.py \
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


FEEDBACK_VERSION = "1.0"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path, label: str | None = None) -> dict[str, Any]:
    if not path.is_file():
        name = label or path.name
        raise FileNotFoundError(f"{name} not found in {path.parent}")
    return json.loads(path.read_text(encoding="utf-8"))


def _read_optional_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
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
        "path": str(path) if path.is_file() else None,
        "sha256": _sha256(path),
    }


def _feedback_item(
    *,
    feedback_id: str,
    target_asset_type: str,
    severity: str,
    source_artifact: str,
    message: str,
    recommended_action: str,
    evidence: dict[str, Any],
) -> dict[str, Any]:
    return {
        "feedback_id": feedback_id,
        "target_asset_type": target_asset_type,
        "status": "open",
        "severity": severity,
        "source_artifact": source_artifact,
        "message": message,
        "recommended_action": recommended_action,
        "evidence": evidence,
    }


def _human_review_feedback(changes: dict[str, Any] | None) -> dict[str, Any] | None:
    if not changes:
        return None
    summary = changes.get("summary", {})
    undecided = int(summary.get("undecided_items", 0) or 0)
    accepted = int(summary.get("accepted_change_count", 0) or 0)
    if undecided <= 0:
        return None
    return _feedback_item(
        feedback_id="semantic-feedback-human-review-pending",
        target_asset_type="governance_review_workspace",
        severity="high",
        source_artifact="accepted_governance_changes.json",
        message=f"{undecided} governance review item(s) remain undecided.",
        recommended_action=(
            "Record human review decisions before building accepted ontology "
            "drafts."
        ),
        evidence={
            "undecided_items": undecided,
            "accepted_change_count": accepted,
        },
    )


def _draft_feedback(drafts: dict[str, Any] | None) -> dict[str, Any] | None:
    if not drafts:
        return None
    summary = drafts.get("summary", {})
    draft_count = int(summary.get("draft_count", 0) or 0)
    if draft_count > 0:
        return None
    return _feedback_item(
        feedback_id="semantic-feedback-no-accepted-drafts",
        target_asset_type="accepted_ontology_drafts",
        severity="medium",
        source_artifact="accepted_ontology_drafts.json",
        message="No accepted ontology drafts are available for package building.",
        recommended_action=(
            "Accept reviewed governance changes, then rebuild accepted "
            "ontology drafts."
        ),
        evidence={
            "draft_count": draft_count,
            "accepted_change_count": int(
                summary.get("accepted_change_count", 0) or 0
            ),
        },
    )


def _package_feedback(package: dict[str, Any] | None) -> dict[str, Any] | None:
    if not package:
        return None
    summary = package.get("summary", {})
    status = summary.get("package_status")
    if status == "BUILT":
        return None
    return _feedback_item(
        feedback_id="semantic-feedback-no-bindable-package",
        target_asset_type="offline_model_package",
        severity="medium",
        source_artifact="offline_model_package.json",
        message=f"Offline model package is not bindable: {status}.",
        recommended_action=(
            "Build a model package only after accepted ontology drafts exist."
        ),
        evidence={
            "package_status": status,
            "source_draft_count": int(summary.get("source_draft_count", 0) or 0),
        },
    )


def _runtime_not_ready_feedback(query_plan: dict[str, Any]) -> dict[str, Any] | None:
    summary = query_plan.get("summary", {})
    query_status = summary.get("query_status")
    if query_status != "NO_RUNTIME_QUERY_READY":
        return None
    return _feedback_item(
        feedback_id="semantic-feedback-runtime-query-not-ready",
        target_asset_type="runtime_query_readiness",
        severity="medium",
        source_artifact="offline_runtime_query_plan.json",
        message="Offline runtime query planning is not ready.",
        recommended_action=(
            "Resolve upstream review, draft, package, and binding gaps before "
            "attempting runtime query activation."
        ),
        evidence={
            "query_status": query_status,
            "binding_status": summary.get("binding_status"),
            "readiness_issue_count": len(query_plan.get("readiness_issues", [])),
        },
    )


def _runtime_activation_feedback(query_plan: dict[str, Any]) -> dict[str, Any] | None:
    summary = query_plan.get("summary", {})
    if summary.get("query_status") != "QUERY_PLANNED":
        return None
    return _feedback_item(
        feedback_id="semantic-feedback-db-backed-runtime-required",
        target_asset_type="runtime_activation",
        severity="medium",
        source_artifact="offline_runtime_query_plan.json",
        message=(
            "Offline query plans exist, but no DB-backed runtime query "
            "was executed."
        ),
        recommended_action=(
            "Promote reviewed package and dataset binding through the "
            "Safety Lane before runtime execution."
        ),
        evidence={
            "query_status": summary.get("query_status"),
            "query_plan_count": int(summary.get("query_plan_count", 0) or 0),
            "executes_runtime_query": bool(
                summary.get("executes_runtime_query", False)
            ),
        },
    )


def _feedback_items(
    *,
    query_plan: dict[str, Any],
    changes: dict[str, Any] | None,
    drafts: dict[str, Any] | None,
    package: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    items = [
        _human_review_feedback(changes),
        _draft_feedback(drafts),
        _package_feedback(package),
        _runtime_not_ready_feedback(query_plan),
        _runtime_activation_feedback(query_plan),
    ]
    return [item for item in items if item is not None]


def _count_by_severity(items: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        severity = str(item.get("severity") or "unknown")
        counts[severity] = counts.get(severity, 0) + 1
    return dict(sorted(counts.items()))


def build_semantic_asset_feedback(data_dir: Path) -> dict[str, Any]:
    query_plan = _read_json(
        data_dir / "offline_runtime_query_plan.json",
        "offline_runtime_query_plan.json",
    )
    changes = _read_optional_json(data_dir / "accepted_governance_changes.json")
    drafts = _read_optional_json(data_dir / "accepted_ontology_drafts.json")
    package = _read_optional_json(data_dir / "offline_model_package.json")
    binding = _read_optional_json(data_dir / "offline_dataset_binding.json")

    items = _feedback_items(
        query_plan=query_plan,
        changes=changes,
        drafts=drafts,
        package=package,
    )
    runtime_query_ready = bool(
        query_plan.get("summary", {}).get("runtime_query_ready", False)
    )
    requires_human_review = bool(items)

    return {
        "feedback_version": FEEDBACK_VERSION,
        "pipeline": "semantic_asset_feedback_loop",
        "generated_at": _utc_now(),
        "data_pack": query_plan.get("data_pack", {"path": str(data_dir)}),
        "source_artifacts": {
            "offline_runtime_query_plan": _artifact(
                data_dir / "offline_runtime_query_plan.json"
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
        },
        "summary": {
            "feedback_status": "BACKLOG_OPEN" if items else "NO_OPEN_FEEDBACK",
            "runtime_query_ready": runtime_query_ready,
            "total_feedback_items": len(items),
            "requires_human_review": requires_human_review,
            "writes_to_database": False,
            "creates_real_governance_issues": False,
            "by_severity": _count_by_severity(items),
        },
        "feedback_items": items,
        "context": {
            "query_summary": query_plan.get("summary", {}),
            "binding_summary": (binding or {}).get("summary", {}),
            "package_summary": (package or {}).get("summary", {}),
            "draft_summary": (drafts or {}).get("summary", {}),
            "accepted_change_summary": (changes or {}).get("summary", {}),
        },
        "boundaries": {
            "offline_only": True,
            "writes_to_database": False,
            "creates_real_governance_issues": False,
            "applies_model_changes": False,
            "publishes_model_package": False,
            "activates_runtime": False,
            "executes_runtime_query": False,
            "requires_human_review": requires_human_review,
        },
    }


def render_markdown(result: dict[str, Any]) -> str:
    summary = result["summary"]
    lines = [
        "# Semantic Asset Feedback Loop",
        "",
        f"- Generated at: `{result['generated_at']}`",
        f"- Data pack: `{result['data_pack']['path']}`",
        f"- Feedback status: `{summary['feedback_status']}`",
        f"- Feedback items: `{summary['total_feedback_items']}`",
        f"- Runtime query ready: `{str(summary['runtime_query_ready']).lower()}`",
        "- Writes to database: `false`",
        "- Creates real governance issues: `false`",
        "",
        "## Feedback Items",
        "",
        "| Feedback | Severity | Target asset | Source | Recommended action |",
        "|---|---|---|---|---|",
    ]
    for item in result["feedback_items"]:
        action = str(item.get("recommended_action") or "").replace("|", "\\|")
        lines.append(
            "| "
            f"{item.get('feedback_id')} | "
            f"{item.get('severity')} | "
            f"{item.get('target_asset_type')} | "
            f"{item.get('source_artifact')} | "
            f"{action} |"
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
            "- Executes runtime query: `false`",
            "",
        ]
    )
    return "\n".join(lines)


def write_semantic_asset_feedback(
    data_dir: Path,
    output_path: Path,
    markdown_output_path: Path | None,
) -> dict[str, Any]:
    result = build_semantic_asset_feedback(data_dir)
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
        description="Build offline semantic asset feedback backlog",
    )
    parser.add_argument(
        "--data-pack",
        type=Path,
        required=True,
        help="Data pack directory containing offline_runtime_query_plan.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=(
            "JSON output path "
            "(default: <data-pack>/semantic_asset_feedback.json)"
        ),
    )
    parser.add_argument(
        "--markdown-output",
        type=Path,
        default=None,
        help=(
            "Markdown output path "
            "(default: <data-pack>/semantic_asset_feedback.md)"
        ),
    )
    args = parser.parse_args()

    output = args.output or (args.data_pack / "semantic_asset_feedback.json")
    markdown_output = (
        args.markdown_output
        if args.markdown_output is not None
        else args.data_pack / "semantic_asset_feedback.md"
    )

    try:
        result = write_semantic_asset_feedback(
            args.data_pack,
            output,
            markdown_output,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    summary = result["summary"]
    print("=== Semantic Asset Feedback Loop ===\n")
    print(f"Data pack: {args.data_pack}")
    print(f"Feedback status: {summary['feedback_status']}")
    print(f"Feedback items: {summary['total_feedback_items']}")
    print(f"Runtime query ready: {summary['runtime_query_ready']}")
    print(f"JSON: {output}")
    print(f"Markdown: {markdown_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
