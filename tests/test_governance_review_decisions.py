"""Tests for applying offline governance review decisions."""

import importlib.util
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "apply_governance_review_decisions.py"


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "apply_governance_review_decisions", SCRIPT_PATH
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _write_workspace(data_dir: Path) -> None:
    _write_json(
        data_dir / "governance_review_workspace.json",
        {
            "workspace_version": "1.0",
            "data_pack": {"path": str(data_dir)},
            "summary": {
                "total_review_items": 2,
                "pending_review_items": 2,
                "requires_human_review": True,
            },
            "review_items": [
                {
                    "review_item_id": "gov-0001",
                    "candidate": {
                        "candidate_id": "gov-0001",
                        "status": "open",
                        "severity": "info",
                        "candidate_types": ["ontology_modeling_opportunity"],
                        "recommended_decision": "consider_modeling",
                        "review_owner_role": "ontology_steward",
                    },
                    "source_record_identity": {
                        "source": "rule_validation_report.json",
                        "table": "equipment",
                        "row": "7",
                        "finding_id": "derived_class-0001",
                        "rule_id": "derived_class",
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
                        "candidate_group_size": 1,
                    },
                    "review_requirements": {
                        "requires_human_review": True,
                        "required_checks": [
                            "confirm_business_meaning",
                            "confirm_not_hard_relation",
                        ],
                    },
                    "rollback_note": "Keep as offline unless accepted.",
                    "evidence_anchors": [
                        {
                            "source": "rule_validation_report.json",
                            "finding_id": "derived_class-0001",
                            "rule_id": "derived_class",
                            "table": "equipment",
                            "row": "7",
                            "column": None,
                            "derived_class": "at_risk_equipment",
                        }
                    ],
                    "decision_record": {
                        "status": "pending",
                        "allowed_decisions": [
                            "accept",
                            "reject",
                            "defer",
                            "needs_more_evidence",
                        ],
                        "decision": None,
                        "reviewer": None,
                        "reviewed_at": None,
                        "rationale": None,
                    },
                },
                {
                    "review_item_id": "gov-0002",
                    "candidate": {
                        "candidate_id": "gov-0002",
                        "status": "open",
                        "severity": "info",
                        "candidate_types": ["ontology_modeling_opportunity"],
                        "recommended_decision": "consider_modeling",
                        "review_owner_role": "ontology_steward",
                    },
                    "source_record_identity": {
                        "source": "rule_validation_report.json",
                        "table": "materials",
                        "row": "11",
                        "finding_id": "derived_class-0002",
                        "rule_id": "derived_class",
                    },
                    "finding": {
                        "finding_id": "derived_class-0002",
                        "rule_id": "derived_class",
                        "table": "materials",
                        "message": "Material classified as high_value_material",
                    },
                    "affected_scope": {
                        "source_table": "materials",
                        "derived_class": "high_value_material",
                        "candidate_group_size": 1,
                    },
                    "review_requirements": {
                        "requires_human_review": True,
                        "required_checks": ["confirm_business_meaning"],
                    },
                    "rollback_note": "Keep as offline unless accepted.",
                    "evidence_anchors": [
                        {
                            "source": "rule_validation_report.json",
                            "finding_id": "derived_class-0002",
                            "rule_id": "derived_class",
                            "table": "materials",
                            "row": "11",
                            "column": None,
                            "derived_class": "high_value_material",
                        }
                    ],
                    "decision_record": {
                        "status": "pending",
                        "allowed_decisions": [
                            "accept",
                            "reject",
                            "defer",
                            "needs_more_evidence",
                        ],
                        "decision": None,
                        "reviewer": None,
                        "reviewed_at": None,
                        "rationale": None,
                    },
                },
            ],
            "boundaries": {
                "offline_only": True,
                "writes_to_database": False,
                "creates_real_governance_issues": False,
                "applies_model_changes": False,
                "publishes_model_package": False,
                "requires_human_review": True,
            },
        },
    )


def _write_decisions(data_dir: Path) -> None:
    _write_json(
        data_dir / "governance_review_decisions.json",
        {
            "decision_version": "1.0",
            "review_batch": "tiny-review",
            "decisions": [
                {
                    "review_item_id": "gov-0001",
                    "decision": "accept",
                    "reviewer": "alice",
                    "reviewed_at": "2026-07-09T08:00:00+00:00",
                    "rationale": "Equipment risk class is useful for pilot review.",
                },
                {
                    "review_item_id": "gov-0002",
                    "decision": "reject",
                    "reviewer": "alice",
                    "reviewed_at": "2026-07-09T08:05:00+00:00",
                    "rationale": "ABC class alone is insufficient evidence.",
                },
            ],
        },
    )


def test_apply_review_decisions_outputs_only_accepted_changes(tmp_path):
    mod = _load_module()
    _write_workspace(tmp_path)
    _write_decisions(tmp_path)

    result = mod.apply_review_decisions(tmp_path)

    assert result["change_version"] == "1.0"
    assert result["pipeline"] == "governance_review_decisions"
    assert result["summary"] == {
        "workspace_items": 2,
        "submitted_decisions": 2,
        "accepted_decisions": 1,
        "rejected_decisions": 1,
        "deferred_decisions": 0,
        "needs_more_evidence_decisions": 0,
        "accepted_change_count": 1,
        "undecided_items": 0,
    }
    assert result["boundaries"] == {
        "offline_only": True,
        "writes_to_database": False,
        "creates_real_governance_issues": False,
        "applies_model_changes": False,
        "publishes_model_package": False,
        "hard_reasoning_allowed": False,
        "requires_human_review": True,
    }

    accepted = result["accepted_changes"]
    assert len(accepted) == 1
    assert accepted[0]["change_id"] == "accepted-gov-0001"
    assert accepted[0]["source_review_item_id"] == "gov-0001"
    assert accepted[0]["status"] == "accepted_for_draft"
    assert accepted[0]["change_type"] == "derived_class_candidate"
    assert accepted[0]["target"] == {
        "source_table": "equipment",
        "derived_class": "at_risk_equipment",
    }
    assert accepted[0]["review"] == {
        "decision": "accept",
        "reviewer": "alice",
        "reviewed_at": "2026-07-09T08:00:00+00:00",
        "rationale": "Equipment risk class is useful for pilot review.",
    }
    assert accepted[0]["hard_reasoning_allowed"] is False

    by_id = {item["review_item_id"]: item for item in result["decision_results"]}
    assert by_id["gov-0001"]["result_status"] == "accepted_for_draft"
    assert by_id["gov-0002"]["result_status"] == "rejected"
    assert "source_path" not in json.dumps(result)
    assert "storage_path" not in json.dumps(result)


def test_unknown_or_invalid_review_decision_fails(tmp_path):
    mod = _load_module()
    _write_workspace(tmp_path)
    _write_json(
        tmp_path / "governance_review_decisions.json",
        {
            "decision_version": "1.0",
            "decisions": [
                {
                    "review_item_id": "gov-9999",
                    "decision": "accept",
                    "reviewer": "alice",
                    "rationale": "unknown id",
                },
                {
                    "review_item_id": "gov-0001",
                    "decision": "approve",
                    "reviewer": "alice",
                    "rationale": "invalid decision value",
                },
            ],
        },
    )

    try:
        mod.apply_review_decisions(tmp_path)
    except ValueError as exc:
        message = str(exc)
    else:
        raise AssertionError("Expected invalid decisions to raise ValueError")

    assert "unknown review_item_id: gov-9999" in message
    assert "invalid decision for gov-0001: approve" in message


def test_write_accepted_changes_outputs_json_and_markdown(tmp_path):
    mod = _load_module()
    _write_workspace(tmp_path)
    _write_decisions(tmp_path)
    json_path = tmp_path / "accepted.json"
    markdown_path = tmp_path / "accepted.md"

    result = mod.write_accepted_changes(tmp_path, json_path, markdown_path)

    assert json.loads(json_path.read_text(encoding="utf-8")) == result
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "# Accepted Governance Changes" in markdown
    assert "accepted-gov-0001" in markdown
    assert "at_risk_equipment" in markdown
    assert "Hard reasoning allowed: `false`" in markdown
