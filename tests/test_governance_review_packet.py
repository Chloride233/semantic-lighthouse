"""Tests for offline governance candidate review packet generation."""

import importlib.util
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "build_governance_review_packet.py"


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "build_governance_review_packet", SCRIPT_PATH
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _write_tiny_feedback(data_dir: Path) -> None:
    _write_json(
        data_dir / "semantic_ci_report.json",
        {
            "report_version": "1.0",
            "pipeline": "semantic_ci",
            "summary": {
                "gate_status": "WARN",
                "hard_failures": 0,
                "warnings": 1,
                "total_candidates": 2,
                "critical_candidates": 0,
            },
            "boundaries": {
                "offline_only": True,
                "writes_to_database": False,
                "creates_real_governance_issues": False,
            },
        },
    )
    _write_json(
        data_dir / "governance_feedback.json",
        {
            "feedback_version": "1.0",
            "summary": {
                "total_candidates": 2,
                "by_type": {
                    "ontology_modeling_opportunity": 1,
                    "data_quality_issue": 1,
                    "mapping_review": 1,
                },
                "by_severity": {"critical": 0, "high": 1, "info": 1},
                "by_table": {"equipment": 1, "work_orders": 1},
                "requires_human_review": True,
            },
            "candidates": [
                {
                    "candidate_id": "gov-0001",
                    "finding_ref": {
                        "finding_id": "derived_class-0001",
                        "rule_id": "derived_class",
                        "table": "equipment",
                        "message": "Entity classified as at_risk_equipment",
                    },
                    "candidate_types": ["ontology_modeling_opportunity"],
                    "severity": "info",
                    "suggested_action": "Consider creating a derived class.",
                    "status": "open",
                    "evidence": {
                        "source": "rule_validation_report.json",
                        "finding_id": "derived_class-0001",
                        "rule_id": "derived_class",
                        "table": "equipment",
                        "row": "7",
                        "column": None,
                        "derived_class": "at_risk_equipment",
                        "detail": "Equipment with degraded status",
                    },
                },
                {
                    "candidate_id": "gov-0002",
                    "finding_ref": {
                        "finding_id": "date_order-0001",
                        "rule_id": "date_order",
                        "table": "work_orders",
                        "message": "scheduled_start > scheduled_end",
                    },
                    "candidate_types": ["data_quality_issue", "mapping_review"],
                    "severity": "high",
                    "suggested_action": "Review date ordering.",
                    "status": "open",
                    "evidence": {
                        "source": "rule_validation_report.json",
                        "finding_id": "date_order-0001",
                        "rule_id": "date_order",
                        "table": "work_orders",
                        "row": "3",
                        "column": "scheduled_start <= scheduled_end",
                        "detail": "start exceeds end",
                    },
                },
            ],
        },
    )


def test_build_review_packet_groups_candidates_and_recommends_checks(tmp_path):
    mod = _load_module()
    _write_tiny_feedback(tmp_path)

    packet = mod.build_review_packet(tmp_path)

    assert packet["packet_version"] == "1.0"
    assert packet["pipeline"] == "governance_candidate_review"
    assert packet["summary"]["total_review_items"] == 2
    assert packet["summary"]["requires_human_review"] is True
    assert packet["boundaries"] == {
        "offline_only": True,
        "writes_to_database": False,
        "creates_real_governance_issues": False,
        "requires_human_review": True,
    }

    by_id = {item["candidate_id"]: item for item in packet["review_items"]}
    assert by_id["gov-0001"]["recommended_decision"] == "consider_modeling"
    assert by_id["gov-0001"]["review_owner_role"] == "ontology_steward"
    assert by_id["gov-0001"]["required_checks"] == [
        "confirm_business_meaning",
        "confirm_not_hard_relation",
        "decide_modeling_action",
    ]
    assert by_id["gov-0002"]["recommended_decision"] == "fix_or_explain_data"
    assert by_id["gov-0002"]["review_owner_role"] == "data_steward"
    assert "verify_source_record" in by_id["gov-0002"]["required_checks"]
    assert by_id["gov-0002"]["evidence_anchor"] == {
        "source": "rule_validation_report.json",
        "finding_id": "date_order-0001",
        "rule_id": "date_order",
        "table": "work_orders",
        "row": "3",
        "column": "scheduled_start <= scheduled_end",
        "derived_class": None,
    }


def test_write_review_packet_outputs_json_and_markdown(tmp_path):
    mod = _load_module()
    _write_tiny_feedback(tmp_path)

    json_path = tmp_path / "review.json"
    markdown_path = tmp_path / "review.md"
    packet = mod.write_review_packet(tmp_path, json_path, markdown_path)

    assert json.loads(json_path.read_text(encoding="utf-8")) == packet
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "# Governance Candidate Review Packet" in markdown
    assert "gov-0001" in markdown
    assert "consider_modeling" in markdown
    assert "fix_or_explain_data" in markdown
