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
from inspect_governance_decision_csv import (  # noqa: E402
    write_governance_decision_csv_inspection,
)
from precheck_governance_review_decisions import write_decision_precheck  # noqa: E402


REPORT_VERSION = "1.0"
DEFAULT_DECISION_CONTEXT = {
    "decision_mode": "not_available",
    "not_enterprise_human_review": False,
    "public_benchmark_fixture_only": False,
}


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


def _decision_context_from_decisions(decisions: dict[str, Any]) -> dict[str, Any]:
    boundaries = decisions.get("boundaries", {})
    benchmark = decisions.get("benchmark", {})
    is_public_fixture = (
        decisions.get("pipeline") == "public_benchmark_governance_decisions"
        or benchmark.get("decision_mode") == "public_benchmark_fixture"
        or boundaries.get("public_benchmark_fixture_only") is True
    )
    if is_public_fixture:
        return {
            "decision_mode": "public_benchmark_fixture",
            "not_enterprise_human_review": True,
            "public_benchmark_fixture_only": True,
        }
    if decisions.get("decisions"):
        return {
            "decision_mode": "human_review",
            "not_enterprise_human_review": False,
            "public_benchmark_fixture_only": False,
        }
    return dict(DEFAULT_DECISION_CONTEXT)


def _decision_context(data_dir: Path, precheck: dict[str, Any] | None) -> dict[str, Any]:
    source_artifacts = precheck.get("source_artifacts", {}) if precheck else {}
    path_text = source_artifacts.get("governance_review_decisions")
    path = Path(path_text) if path_text else data_dir / "governance_review_decisions.json"
    if not path.is_file():
        return dict(DEFAULT_DECISION_CONTEXT)
    return _decision_context_from_decisions(_read_json(path))


def _missing_artifact() -> dict[str, str | None]:
    return {
        "path": None,
        "sha256": None,
    }


def _artifact_map(
    data_dir: Path,
    *,
    include_csv_inspection: bool,
    include_precheck: bool,
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
        "governance_review_decisions_csv_inspection": (
            _artifact(data_dir / "governance_review_decisions_csv_inspection.json")
            if include_csv_inspection
            else _missing_artifact()
        ),
        "governance_review_decisions_precheck": (
            _artifact(data_dir / "governance_review_decisions_precheck.json")
            if include_precheck
            else _missing_artifact()
        ),
        **{
            name: _artifact(path) if include_downstream else _missing_artifact()
            for name, path in downstream_artifacts.items()
        },
    }


def _summary_from_acceptance(
    precheck: dict[str, Any] | None,
    acceptance: dict[str, Any] | None,
    decision_context: dict[str, Any],
) -> dict[str, Any]:
    precheck_summary = precheck.get("summary", {}) if precheck else {}
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
            "decision_mode": decision_context["decision_mode"],
            "not_enterprise_human_review": decision_context[
                "not_enterprise_human_review"
            ],
            "public_benchmark_fixture_only": decision_context[
                "public_benchmark_fixture_only"
            ],
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
        "decision_mode": decision_context["decision_mode"],
        "not_enterprise_human_review": decision_context[
            "not_enterprise_human_review"
        ],
        "public_benchmark_fixture_only": decision_context[
            "public_benchmark_fixture_only"
        ],
    }


def _report(
    *,
    data_dir: Path,
    precheck: dict[str, Any] | None,
    acceptance: dict[str, Any] | None,
    include_csv_inspection: bool = False,
) -> dict[str, Any]:
    decision_context = _decision_context(data_dir, precheck)
    return {
        "report_version": REPORT_VERSION,
        "pipeline": "post_review_semantic_loop",
        "generated_at": _utc_now(),
        "data_pack": (
            acceptance.get("data_pack")
            if acceptance is not None
            else (precheck or {}).get("data_pack", {"path": str(data_dir)})
        ),
        "summary": _summary_from_acceptance(
            precheck,
            acceptance,
            decision_context,
        ),
        "artifacts": _artifact_map(
            data_dir,
            include_csv_inspection=include_csv_inspection,
            include_precheck=precheck is not None,
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
            "not_enterprise_human_review": decision_context[
                "not_enterprise_human_review"
            ],
            "public_benchmark_fixture_only": decision_context[
                "public_benchmark_fixture_only"
            ],
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
    report_path = output_path or (data_dir / "post_review_semantic_loop_report.json")
    if decision_csv_path is not None:
        inspection = write_governance_decision_csv_inspection(
            decision_csv_path,
            data_dir / "governance_review_decisions_csv_inspection.json",
            data_dir / "governance_review_decisions_csv_inspection.md",
        )
        if not inspection["summary"]["ready_for_post_review_runner"]:
            result = _report(
                data_dir=data_dir,
                precheck=None,
                acceptance=None,
                include_csv_inspection=True,
            )
            _write_json(report_path, result)
            return result
        decisions_path = data_dir / "governance_review_decisions.json"
        convert_governance_decision_csv(
            decision_csv_path,
            decisions_path,
            review_batch,
        )

    precheck = write_decision_precheck(
        data_dir,
        data_dir / "governance_review_decisions_precheck.json",
        data_dir / "governance_review_decisions_precheck.md",
        decisions_path,
    )
    if precheck["summary"]["precheck_status"] != "PASS":
        result = _report(
            data_dir=data_dir,
            precheck=precheck,
            acceptance=None,
            include_csv_inspection=decision_csv_path is not None,
        )
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
    result = _report(
        data_dir=data_dir,
        precheck=precheck,
        acceptance=acceptance,
        include_csv_inspection=decision_csv_path is not None,
    )
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
