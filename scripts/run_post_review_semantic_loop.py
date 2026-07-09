"""Run the offline post-review semantic loop.

This CLI starts after human-authored governance decisions exist. It validates
the decisions, then builds accepted changes, accepted ontology drafts, offline
model package, dataset binding, runtime query dry run, semantic asset feedback,
and the final offline acceptance report.

It does not write to the database, create governance issues, publish packages,
activate runtime, execute runtime queries, or auto-accept candidates.

Usage:
  .venv/Scripts/python scripts/run_post_review_semantic_loop.py \
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


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from apply_governance_review_decisions import write_accepted_changes  # noqa: E402
from build_accepted_ontology_drafts import write_accepted_ontology_drafts  # noqa: E402
from build_offline_acceptance_report import write_offline_acceptance_report  # noqa: E402
from build_offline_dataset_binding import write_offline_dataset_binding  # noqa: E402
from build_offline_model_package import write_offline_model_package  # noqa: E402
from build_offline_runtime_query_plan import write_offline_runtime_query_plan  # noqa: E402
from build_semantic_asset_feedback import write_semantic_asset_feedback  # noqa: E402
from convert_governance_decision_csv import convert_governance_decision_csv  # noqa: E402
from precheck_governance_review_decisions import write_decision_precheck  # noqa: E402


REPORT_VERSION = "1.0"


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


def _sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _artifact(path: Path) -> dict[str, str | None]:
    if not path.is_file():
        return {
            "path": None,
            "sha256": None,
        }
    return {
        "path": str(path),
        "sha256": _sha256(path),
    }


def _missing_artifact() -> dict[str, str | None]:
    return {
        "path": None,
        "sha256": None,
    }


def _artifact_map(
    data_dir: Path,
    *,
    include_downstream: bool,
) -> dict[str, dict[str, str | None]]:
    downstream_artifacts = {
        "accepted_governance_changes": data_dir / "accepted_governance_changes.json",
        "accepted_ontology_drafts": data_dir / "accepted_ontology_drafts.json",
        "offline_model_package": data_dir / "offline_model_package.json",
        "offline_dataset_binding": data_dir / "offline_dataset_binding.json",
        "offline_runtime_query_plan": data_dir / "offline_runtime_query_plan.json",
        "semantic_asset_feedback": data_dir / "semantic_asset_feedback.json",
        "offline_acceptance_report": data_dir / "offline_acceptance_report.json",
    }
    return {
        "governance_review_decisions_precheck": _artifact(
            data_dir / "governance_review_decisions_precheck.json"
        ),
        **{
            name: _artifact(path) if include_downstream else _missing_artifact()
            for name, path in downstream_artifacts.items()
        },
    }


def _summary_from_acceptance(
    precheck: dict[str, Any],
    acceptance: dict[str, Any] | None,
) -> dict[str, Any]:
    precheck_summary = precheck.get("summary", {})
    if acceptance is None:
        precheck_status = precheck_summary.get("precheck_status")
        return {
            "run_status": "FAIL",
            "precheck_status": precheck_status,
            "chain_status": (
                "PRECHECK_FAILED"
                if precheck_status == "FAIL"
                else "REVIEW_INCOMPLETE"
            ),
            "accepted_change_count": 0,
            "draft_count": 0,
            "package_status": None,
            "binding_status": None,
            "query_status": None,
            "feedback_status": None,
        }

    acceptance_summary = acceptance.get("summary", {})
    return {
        "run_status": "PASS",
        "precheck_status": precheck_summary.get("precheck_status"),
        "chain_status": acceptance_summary.get("chain_status"),
        "accepted_change_count": acceptance_summary.get("accepted_change_count"),
        "draft_count": acceptance_summary.get("draft_count"),
        "package_status": acceptance_summary.get("package_status"),
        "binding_status": acceptance_summary.get("binding_status"),
        "query_status": acceptance_summary.get("query_status"),
        "feedback_status": acceptance_summary.get("feedback_status"),
    }


def _report(
    *,
    data_dir: Path,
    precheck: dict[str, Any],
    acceptance: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "report_version": REPORT_VERSION,
        "pipeline": "post_review_semantic_loop",
        "generated_at": _utc_now(),
        "data_pack": (
            acceptance.get("data_pack")
            if acceptance is not None
            else precheck.get("data_pack", {"path": str(data_dir)})
        ),
        "summary": _summary_from_acceptance(precheck, acceptance),
        "artifacts": _artifact_map(
            data_dir,
            include_downstream=acceptance is not None,
        ),
        "boundaries": {
            "offline_only": True,
            "writes_to_database": False,
            "creates_real_governance_issues": False,
            "applies_model_changes": False,
            "publishes_model_package": False,
            "activates_runtime": False,
            "executes_runtime_query": False,
            "auto_accepts_candidates": False,
            "requires_human_review": True,
            "requires_safety_lane_for_runtime": True,
        },
    }


def run_post_review_semantic_loop(
    data_dir: Path,
    decisions_path: Path | None = None,
    output_path: Path | None = None,
    decision_csv_path: Path | None = None,
    review_batch: str = "csv-review",
) -> dict[str, Any]:
    if decisions_path is not None and decision_csv_path is not None:
        raise ValueError("Use either decisions_path or decision_csv_path, not both")
    if decision_csv_path is not None:
        decisions_path = data_dir / "governance_review_decisions.json"
        convert_governance_decision_csv(
            decision_csv_path,
            decisions_path,
            review_batch,
        )

    report_path = output_path or (data_dir / "post_review_semantic_loop_report.json")
    precheck = write_decision_precheck(
        data_dir,
        data_dir / "governance_review_decisions_precheck.json",
        data_dir / "governance_review_decisions_precheck.md",
        decisions_path,
    )
    if precheck["summary"]["precheck_status"] != "PASS":
        result = _report(data_dir=data_dir, precheck=precheck, acceptance=None)
        _write_json(report_path, result)
        return result

    write_accepted_changes(
        data_dir,
        data_dir / "accepted_governance_changes.json",
        data_dir / "accepted_governance_changes.md",
        decisions_path,
    )
    write_accepted_ontology_drafts(
        data_dir,
        data_dir / "accepted_ontology_drafts.json",
        data_dir / "accepted_ontology_drafts.md",
    )
    write_offline_model_package(
        data_dir,
        data_dir / "offline_model_package.json",
        data_dir / "offline_model_package.md",
    )
    write_offline_dataset_binding(
        data_dir,
        data_dir / "offline_dataset_binding.json",
        data_dir / "offline_dataset_binding.md",
    )
    write_offline_runtime_query_plan(
        data_dir,
        data_dir / "offline_runtime_query_plan.json",
        data_dir / "offline_runtime_query_plan.md",
    )
    write_semantic_asset_feedback(
        data_dir,
        data_dir / "semantic_asset_feedback.json",
        data_dir / "semantic_asset_feedback.md",
    )
    acceptance = write_offline_acceptance_report(
        data_dir,
        data_dir / "offline_acceptance_report.json",
        data_dir / "offline_acceptance_report.md",
    )
    result = _report(data_dir=data_dir, precheck=precheck, acceptance=acceptance)
    _write_json(report_path, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run offline post-review semantic loop",
    )
    parser.add_argument(
        "--data-pack",
        type=Path,
        required=True,
        help="Data pack directory containing governance_review_decisions.json",
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
        "--decision-csv",
        type=Path,
        default=None,
        help=(
            "Filled decision CSV path. When provided, it is converted to "
            "<data-pack>/governance_review_decisions.json before precheck."
        ),
    )
    parser.add_argument(
        "--review-batch",
        default="csv-review",
        help="Review batch label used when converting --decision-csv",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=(
            "JSON report output path "
            "(default: <data-pack>/post_review_semantic_loop_report.json)"
        ),
    )
    args = parser.parse_args()

    try:
        result = run_post_review_semantic_loop(
            args.data_pack,
            args.decisions,
            args.output,
            args.decision_csv,
            args.review_batch,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    summary = result["summary"]
    print("=== Post-Review Semantic Loop ===\n")
    print(f"Data pack: {args.data_pack}")
    print(f"Run status: {summary['run_status']}")
    print(f"Precheck status: {summary['precheck_status']}")
    print(f"Chain status: {summary['chain_status']}")
    print(f"Package status: {summary['package_status']}")
    print(f"Binding status: {summary['binding_status']}")
    print(f"Query status: {summary['query_status']}")
    print(f"Report: {args.output or args.data_pack / 'post_review_semantic_loop_report.json'}")
    return 1 if summary["run_status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
