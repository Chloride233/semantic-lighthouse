"""Tests for post-review offline semantic loop orchestration."""

import csv
import importlib.util
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "run_post_review_semantic_loop.py"
ACCEPTANCE_SCRIPT_PATH = REPO_ROOT / "scripts" / "build_offline_acceptance_report.py"


def _load_module(name: str, path: Path):
    assert path.is_file(), f"missing script: {path.name}"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _write_semantic_ci(data_dir: Path) -> None:
    _write_json(
        data_dir / "semantic_ci_report.json",
        {
            "report_version": "1.0",
            "pipeline": "semantic_ci",
            "data_pack": {
                "path": str(data_dir),
                "preset": "tiny",
                "seed": 7,
                "table_count": 1,
                "total_rows": 2,
            },
            "summary": {
                "gate_status": "WARN",
                "hard_failures": 0,
                "warnings": 1,
                "total_candidates": 1,
                "critical_candidates": 0,
            },
        },
    )


def _write_manifest(data_dir: Path) -> None:
    _write_json(
        data_dir / "manifest.json",
        {
            "preset": "tiny",
            "seed": 7,
            "table_count": 1,
            "total_rows": 2,
            "tables": [
                {
                    "table_name": "equipment",
                    "csv_file": "equipment.csv",
                    "row_count": 2,
                    "primary_key": ["equipment_id"],
                    "core_pilot": True,
                    "business_meaning": "Equipment assets",
                }
            ],
        },
    )


def _write_mapping_contract(data_dir: Path) -> None:
    _write_json(
        data_dir / "mapping_contract.json",
        {
            "object_type_mappings": [
                {
                    "source_table": "equipment",
                    "object_type": "Equipment",
                    "primary_key": ["equipment_id"],
                    "column_mappings": [
                        {
                            "source_column": "equipment_id",
                            "target_property": "equipment_id",
                        },
                        {
                            "source_column": "status",
                            "target_property": "status",
                        },
                    ],
                }
            ]
        },
    )


def _write_workspace(data_dir: Path, pending: int = 1) -> None:
    _write_json(
        data_dir / "governance_review_workspace.json",
        {
            "workspace_version": "1.0",
            "pipeline": "governance_candidate_review_workspace",
            "data_pack": {"path": str(data_dir)},
            "summary": {
                "total_review_items": 1,
                "pending_review_items": pending,
                "requires_human_review": pending > 0,
            },
            "review_items": [
                {
                    "review_item_id": "gov-0001",
                    "candidate": {
                        "severity": "info",
                        "recommended_decision": "consider_modeling",
                        "review_owner_role": "ontology_steward",
                    },
                    "finding": {
                        "finding_id": "derived_class-0001",
                        "rule_id": "derived_class",
                        "table": "equipment",
                        "message": "Equipment classified as at_risk_equipment",
                    },
                    "affected_scope": {
                        "source_table": "equipment",
                        "derived_class": "at_risk_equipment",
                    },
                    "review_requirements": {
                        "requires_human_review": True,
                        "required_checks": ["confirm_business_meaning"],
                    },
                    "rollback_note": "Keep offline unless accepted.",
                    "evidence_anchors": [
                        {
                            "source": "rule_validation_report.json",
                            "finding_id": "derived_class-0001",
                            "rule_id": "derived_class",
                            "table": "equipment",
                            "row": "1",
                        }
                    ],
                }
            ],
        },
    )


def _write_valid_decisions(data_dir: Path) -> None:
    _write_json(
        data_dir / "governance_review_decisions.json",
        {
            "decision_version": "1.0",
            "review_batch": "tiny-review",
            "decisions": [
                {
                    "review_item_id": "gov-0001",
                    "decision": "accept",
                    "reviewer": "ontology_steward",
                    "reviewed_at": "2026-07-09T08:00:00+00:00",
                    "rationale": "Accepted for offline draft generation.",
                }
            ],
        },
    )


def _write_invalid_decisions(data_dir: Path) -> None:
    _write_json(
        data_dir / "governance_review_decisions.json",
        {
            "decision_version": "1.0",
            "decisions": [
                {
                    "review_item_id": "gov-0001",
                    "decision": "accept",
                    "reviewer": "",
                    "reviewed_at": "",
                    "rationale": "",
                }
            ],
        },
    )


def _write_filled_decision_csv(path: Path) -> None:
    rows = [
        {
            "review_item_id": "gov-0001",
            "decision": "accept",
            "reviewer": "ontology_steward",
            "reviewed_at": "2026-07-09T08:00:00+00:00",
            "rationale": "Accepted for offline draft generation.",
            "recommended_decision": "consider_modeling",
            "review_owner_role": "ontology_steward",
            "severity": "info",
            "source_table": "equipment",
            "derived_class": "at_risk_equipment",
            "finding_id": "derived_class-0001",
            "rule_id": "derived_class",
            "finding_message": "Equipment classified as at_risk_equipment",
            "required_checks": "confirm_business_meaning",
            "evidence_anchor": "",
        }
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _write_blank_decision_csv(path: Path) -> None:
    rows = [
        {
            "review_item_id": "gov-0001",
            "decision": "",
            "reviewer": "",
            "reviewed_at": "",
            "rationale": "",
            "recommended_decision": "consider_modeling",
            "review_owner_role": "ontology_steward",
            "severity": "info",
            "source_table": "equipment",
            "derived_class": "at_risk_equipment",
            "finding_id": "derived_class-0001",
            "rule_id": "derived_class",
            "finding_message": "Equipment classified as at_risk_equipment",
            "required_checks": "confirm_business_meaning",
            "evidence_anchor": "",
        }
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _write_required_inputs(data_dir: Path) -> None:
    _write_semantic_ci(data_dir)
    _write_manifest(data_dir)
    _write_mapping_contract(data_dir)
    _write_workspace(data_dir)


def test_post_review_loop_accepts_filled_decision_csv(tmp_path):
    mod = _load_module("run_post_review_semantic_loop", SCRIPT_PATH)
    _write_required_inputs(tmp_path)
    csv_path = tmp_path / "governance_review_decisions_template.csv"
    _write_filled_decision_csv(csv_path)

    result = mod.run_post_review_semantic_loop(
        tmp_path,
        decision_csv_path=csv_path,
        review_batch="csv-pilot-review",
    )

    decisions = json.loads(
        (tmp_path / "governance_review_decisions.json").read_text(
            encoding="utf-8"
        )
    )
    assert decisions["pipeline"] == "governance_review_decision_csv"
    assert decisions["review_batch"] == "csv-pilot-review"
    assert result["summary"]["run_status"] == "PASS"
    assert result["summary"]["chain_status"] == "READY_FOR_SAFETY_LANE"


def test_post_review_loop_stops_when_csv_review_is_incomplete(tmp_path):
    mod = _load_module("run_post_review_semantic_loop", SCRIPT_PATH)
    _write_required_inputs(tmp_path)
    csv_path = tmp_path / "governance_review_decisions_template.csv"
    _write_blank_decision_csv(csv_path)

    result = mod.run_post_review_semantic_loop(
        tmp_path,
        decision_csv_path=csv_path,
        review_batch="csv-pilot-review",
    )

    assert result["summary"]["run_status"] == "FAIL"
    assert result["summary"]["precheck_status"] == "WARN"
    assert result["summary"]["chain_status"] == "REVIEW_INCOMPLETE"
    assert (tmp_path / "governance_review_decisions_precheck.json").is_file()
    assert not (tmp_path / "accepted_governance_changes.json").exists()
    assert result["artifacts"]["accepted_governance_changes"]["path"] is None


def test_post_review_loop_builds_downstream_artifacts_after_valid_decisions(tmp_path):
    mod = _load_module("run_post_review_semantic_loop", SCRIPT_PATH)
    _write_required_inputs(tmp_path)
    _write_valid_decisions(tmp_path)

    result = mod.run_post_review_semantic_loop(tmp_path)

    assert result["pipeline"] == "post_review_semantic_loop"
    assert result["summary"]["run_status"] == "PASS"
    assert result["summary"]["precheck_status"] == "PASS"
    assert result["summary"]["chain_status"] == "READY_FOR_SAFETY_LANE"
    assert result["summary"]["accepted_change_count"] == 1
    assert result["summary"]["draft_count"] == 1
    assert result["summary"]["package_status"] == "BUILT"
    assert result["summary"]["binding_status"] == "BOUND"
    assert result["summary"]["query_status"] == "QUERY_PLANNED"
    assert result["boundaries"] == {
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
    }
    for artifact in result["artifacts"].values():
        assert artifact["path"]
        assert artifact["sha256"]
        assert Path(artifact["path"]).is_file()
    assert json.loads(
        (tmp_path / "post_review_semantic_loop_report.json").read_text(
            encoding="utf-8"
        )
    ) == result


def test_post_review_loop_stops_before_apply_when_precheck_fails(tmp_path):
    mod = _load_module("run_post_review_semantic_loop", SCRIPT_PATH)
    _write_required_inputs(tmp_path)
    _write_invalid_decisions(tmp_path)

    result = mod.run_post_review_semantic_loop(tmp_path)

    assert result["summary"]["run_status"] == "FAIL"
    assert result["summary"]["precheck_status"] == "FAIL"
    assert result["summary"]["chain_status"] == "PRECHECK_FAILED"
    assert (tmp_path / "governance_review_decisions_precheck.json").is_file()
    assert not (tmp_path / "accepted_governance_changes.json").exists()
    assert result["artifacts"]["accepted_governance_changes"]["path"] is None


def test_acceptance_report_uses_applied_decisions_when_workspace_pending_is_stale(
    tmp_path,
):
    mod = _load_module("build_offline_acceptance_report", ACCEPTANCE_SCRIPT_PATH)
    _write_semantic_ci(tmp_path)
    _write_workspace(tmp_path, pending=1)
    _write_json(
        tmp_path / "accepted_governance_changes.json",
        {
            "change_version": "1.0",
            "pipeline": "governance_review_decisions",
            "data_pack": {"path": str(tmp_path)},
            "summary": {
                "workspace_items": 1,
                "submitted_decisions": 1,
                "accepted_change_count": 1,
                "undecided_items": 0,
            },
        },
    )
    _write_json(
        tmp_path / "accepted_ontology_drafts.json",
        {
            "draft_artifact_version": "1.0",
            "pipeline": "accepted_ontology_drafts",
            "data_pack": {"path": str(tmp_path)},
            "summary": {"draft_count": 1, "derived_class_draft_count": 1},
        },
    )
    _write_json(
        tmp_path / "offline_model_package.json",
        {
            "package_artifact_version": "1.0",
            "pipeline": "offline_model_package_bridge",
            "data_pack": {"path": str(tmp_path)},
            "summary": {
                "package_status": "BUILT",
                "source_draft_count": 1,
                "derived_class_count": 1,
            },
        },
    )
    _write_json(
        tmp_path / "offline_dataset_binding.json",
        {
            "binding_artifact_version": "1.0",
            "pipeline": "offline_dataset_binding_bridge",
            "data_pack": {"path": str(tmp_path)},
            "summary": {
                "binding_status": "BOUND",
                "binding_count": 1,
                "runtime_query_ready": True,
            },
        },
    )
    _write_json(
        tmp_path / "offline_runtime_query_plan.json",
        {
            "query_plan_version": "1.0",
            "pipeline": "offline_runtime_query_dry_run",
            "data_pack": {"path": str(tmp_path)},
            "summary": {
                "query_status": "QUERY_PLANNED",
                "query_plan_count": 1,
                "executes_runtime_query": False,
            },
        },
    )
    _write_json(
        tmp_path / "semantic_asset_feedback.json",
        {
            "feedback_version": "1.0",
            "pipeline": "semantic_asset_feedback_loop",
            "data_pack": {
                "path": str(tmp_path),
                "table_count": 1,
                "total_rows": 2,
            },
            "summary": {
                "feedback_status": "BACKLOG_OPEN",
                "total_feedback_items": 1,
                "requires_human_review": True,
            },
        },
    )

    result = mod.build_offline_acceptance_report(tmp_path)

    assert result["summary"]["pending_review_items"] == 0
    assert result["summary"]["chain_status"] == "READY_FOR_SAFETY_LANE"
    assert result["stages"][1] == {
        "stage": "governance_review",
        "status": "REVIEW_COMPLETE",
        "evidence": {
            "total_review_items": 1,
            "pending_review_items": 0,
        },
    }
