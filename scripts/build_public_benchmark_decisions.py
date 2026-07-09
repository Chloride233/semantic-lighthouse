"""Build public benchmark governance decision fixtures.

This script creates a governance_review_decisions.json file for public sample
data only. It is explicitly not enterprise human review. It lets benchmark
packs exercise the offline post-review semantic loop without pretending that a
business owner approved real production semantics.

Usage:
  .venv/Scripts/python scripts/build_public_benchmark_decisions.py \
      --data-pack .tmp/adventureworks-semantic
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DECISION_VERSION = "1.0"
REVIEW_BATCH = "public-benchmark-fixture"
REVIEWER = "public_benchmark_fixture"
EVIDENCE_BASIS = [
    "public_sample_schema",
    "data_pack_manifest",
    "mapping_contract",
    "rule_validation_report",
    "governance_review_workspace",
]
UNSAFE_KEYS = {"source_path", "storage_path"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"{label} not found at {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _sanitize(item)
            for key, item in value.items()
            if key not in UNSAFE_KEYS
        }
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    return value


def _workspace(data_dir: Path) -> dict[str, Any]:
    return _read_json(
        data_dir / "governance_review_workspace.json",
        "governance_review_workspace.json",
    )


def _is_benchmark_acceptable(item: dict[str, Any]) -> bool:
    scope = item.get("affected_scope", {})
    candidate = item.get("candidate", {})
    return (
        bool(scope.get("derived_class"))
        and candidate.get("recommended_decision") == "consider_modeling"
    )


def _decision_for_item(item: dict[str, Any]) -> str:
    if _is_benchmark_acceptable(item):
        return "accept"
    return "needs_more_evidence"


def _rationale(item: dict[str, Any], benchmark_name: str) -> str:
    scope = item.get("affected_scope", {})
    derived_class = scope.get("derived_class")
    source_table = scope.get("source_table")
    if _is_benchmark_acceptable(item):
        return (
            f"Accepted as a public benchmark fixture for {benchmark_name}: "
            f"{source_table}.{derived_class} is a derived-class modeling "
            "candidate supported by public sample schema and offline rule "
            "evidence. This is not a real enterprise human approval."
        )
    return (
        f"Needs more evidence in public benchmark fixture for {benchmark_name}: "
        "this review item is not a derived-class modeling candidate with a "
        "consider_modeling recommendation. This is not a real enterprise "
        "human approval."
    )


def _decision(item: dict[str, Any], benchmark_name: str, reviewed_at: str) -> dict[str, Any]:
    return {
        "review_item_id": item.get("review_item_id"),
        "decision": _decision_for_item(item),
        "reviewer": REVIEWER,
        "reviewed_at": reviewed_at,
        "rationale": _rationale(item, benchmark_name),
        "decision_mode": "public_benchmark_fixture",
        "not_enterprise_human_review": True,
        "evidence_basis": EVIDENCE_BASIS,
    }


def _count(decisions: list[dict[str, Any]], decision: str) -> int:
    return sum(1 for item in decisions if item.get("decision") == decision)


def build_public_benchmark_decisions(
    data_dir: Path,
    *,
    benchmark_name: str = "AdventureWorks public benchmark",
) -> dict[str, Any]:
    workspace = _workspace(data_dir)
    reviewed_at = _utc_now()
    decisions = [
        _decision(item, benchmark_name, reviewed_at)
        for item in workspace.get("review_items", [])
    ]
    result = {
        "decision_version": DECISION_VERSION,
        "pipeline": "public_benchmark_governance_decisions",
        "generated_at": reviewed_at,
        "review_batch": REVIEW_BATCH,
        "data_pack": workspace.get("data_pack", {"path": str(data_dir)}),
        "source_artifacts": {
            "governance_review_workspace": str(
                data_dir / "governance_review_workspace.json"
            ),
        },
        "benchmark": {
            "name": benchmark_name,
            "decision_mode": "public_benchmark_fixture",
            "evidence_basis": EVIDENCE_BASIS,
            "not_enterprise_human_review": True,
        },
        "summary": {
            "workspace_items": len(workspace.get("review_items", [])),
            "submitted_decisions": len(decisions),
            "accepted_decisions": _count(decisions, "accept"),
            "deferred_decisions": _count(decisions, "defer"),
            "needs_more_evidence_decisions": _count(
                decisions,
                "needs_more_evidence",
            ),
        },
        "decisions": decisions,
        "boundaries": {
            "offline_only": True,
            "writes_to_database": False,
            "creates_real_governance_issues": False,
            "applies_model_changes": False,
            "publishes_model_package": False,
            "activates_runtime": False,
            "executes_runtime_query": False,
            "auto_accepts_candidates": False,
            "not_enterprise_human_review": True,
            "public_benchmark_fixture_only": True,
        },
    }
    return _sanitize(result)


def render_markdown(result: dict[str, Any]) -> str:
    summary = result["summary"]
    benchmark = result["benchmark"]
    lines = [
        "# Public Benchmark Governance Decisions",
        "",
        f"- Generated at: `{result['generated_at']}`",
        f"- Benchmark: `{benchmark['name']}`",
        f"- Decision mode: `{benchmark['decision_mode']}`",
        "- Not enterprise human review: `true`",
        f"- Submitted decisions: `{summary['submitted_decisions']}`",
        f"- Accepted decisions: `{summary['accepted_decisions']}`",
        f"- Needs more evidence: `{summary['needs_more_evidence_decisions']}`",
        "",
        "## Decisions",
        "",
        "| Review item | Decision | Reviewer |",
        "|---|---|---|",
    ]
    for decision in result["decisions"]:
        lines.append(
            "| "
            f"{decision.get('review_item_id')} | "
            f"{decision.get('decision')} | "
            f"{decision.get('reviewer')} |"
        )
    lines.extend(
        [
            "",
            "## Boundaries",
            "",
            "- Offline only: `true`",
            "- Writes to database: `false`",
            "- Auto accepts candidates: `false`",
            "- Public benchmark fixture only: `true`",
            "- These decisions can exercise the offline chain, but they are not "
            "production semantic approvals.",
            "",
        ]
    )
    return "\n".join(lines)


def write_public_benchmark_decisions(
    data_dir: Path,
    output_path: Path,
    markdown_output_path: Path | None,
    *,
    benchmark_name: str = "AdventureWorks public benchmark",
) -> dict[str, Any]:
    result = build_public_benchmark_decisions(
        data_dir,
        benchmark_name=benchmark_name,
    )
    _write_json(output_path, result)
    if markdown_output_path is not None:
        markdown_output_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_output_path.write_text(render_markdown(result), encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build public benchmark governance decision fixture",
    )
    parser.add_argument(
        "--data-pack",
        type=Path,
        required=True,
        help="Data pack directory containing governance_review_workspace.json",
    )
    parser.add_argument(
        "--benchmark-name",
        default="AdventureWorks public benchmark",
        help="Public benchmark name written to the decision artifact",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=(
            "JSON output path "
            "(default: <data-pack>/governance_review_decisions.json)"
        ),
    )
    parser.add_argument(
        "--markdown-output",
        type=Path,
        default=None,
        help=(
            "Markdown output path "
            "(default: <data-pack>/governance_review_decisions.md)"
        ),
    )
    args = parser.parse_args()

    output = args.output or (args.data_pack / "governance_review_decisions.json")
    markdown_output = (
        args.markdown_output
        if args.markdown_output is not None
        else args.data_pack / "governance_review_decisions.md"
    )

    try:
        result = write_public_benchmark_decisions(
            args.data_pack,
            output,
            markdown_output,
            benchmark_name=args.benchmark_name,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    summary = result["summary"]
    print("=== Public Benchmark Governance Decisions ===\n")
    print(f"Data pack: {args.data_pack}")
    print(f"Benchmark: {args.benchmark_name}")
    print(f"Submitted decisions: {summary['submitted_decisions']}")
    print(f"Accepted decisions: {summary['accepted_decisions']}")
    print(f"Needs more evidence: {summary['needs_more_evidence_decisions']}")
    print(f"JSON: {output}")
    print(f"Markdown: {markdown_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

