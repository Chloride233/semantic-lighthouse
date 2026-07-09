"""Tests for offline governance candidate review workspace generation."""

import importlib.util
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "build_governance_review_workspace.py"


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "build_governance_review_workspace", SCRIPT_PATH
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _write_tiny_artifacts(data_dir: Path) -> None:
    _write_json(
        data_dir / "governance_review_packet.json",
        {
            "packet_version": "1.0",
            "data_pack": {"path": str(data_dir)},
            "summary": {
                "total_review_items": 2,
                "requires_human_review": True,
            },
            "review_items": [
                {
                    "candidate_id": "gov-0001",
                    "status": "open",
                    "severity": "info",
                    "candidate_types": ["ontology_modeling_opportunity"],
                    "finding": {
                        "finding_id": "derived_class-0001",
                        "rule_id": "derived_class",
                        "table": "equipment",
                        "message": "Equipment classified as at_risk_equipment",
                    },
                    "suggested_action": "Consider creating a derived class.",
                    "recommended_decision": "consider_modeling",
                    "review_owner_role": "ontology_steward",
                    "required_checks": [
                        "confirm_business_meaning",
                        "confirm_not_hard_relation",
                    ],
                    "rollback_note": "Keep as an offline candidate unless accepted.",
                    "evidence_anchor": {
                        "source": "rule_validation_report.json",
                        "finding_id": "derived_class-0001",
                        "rule_id": "derived_class",
                        "table": "equipment",
                        "row": "7",
                        "column": None,
                        "derived_class": "at_risk_equipment",
                    },
                },
                {
                    "candidate_id": "gov-0002",
                    "status": "open",
                    "severity": "info",
                    "candidate_types": ["ontology_modeling_opportunity"],
                    "finding": {
                        "finding_id": "derived_class-0002",
                        "rule_id": "derived_class",
                        "table": "materials",
                        "message": "Material classified as high_value_material",
                    },
                    "suggested_action": "Consider creating a derived class.",
                    "recommended_decision": "consider_modeling",
                    "review_owner_role": "ontology_steward",
                    "required_checks": ["confirm_business_meaning"],
                    "rollback_note": "Keep as an offline candidate unless accepted.",
                    "evidence_anchor": {
                        "source": "rule_validation_report.json",
                        "finding_id": "derived_class-0002",
                        "rule_id": "derived_class",
                        "table": "materials",
                        "row": "11",
                        "column": None,
                        "derived_class": "high_value_material",
                    },
                },
            ],
        },
    )
    _write_json(
        data_dir / "adventureworks_ontology_seed.json",
        {
            "seed_version": "1.0",
            "summary": {
                "object_type_count": 2,
                "relationship_count": 1,
                "derived_class_count": 2,
                "review_candidate_count": 2,
                "requires_human_review": True,
            },
            "derived_classes": [
                {
                    "derived_class": "at_risk_equipment",
                    "source_table": "equipment",
                    "candidate_ids": ["gov-0001"],
                },
                {
                    "derived_class": "high_value_material",
                    "source_table": "materials",
                    "candidate_ids": ["gov-0002"],
                },
            ],
        },
    )


def test_build_review_workspace_adds_decision_records_and_scope(tmp_path):
    mod = _load_module()
    _write_tiny_artifacts(tmp_path)

    workspace = mod.build_review_workspace(tmp_path)

    assert workspace["workspace_version"] == "1.0"
    assert workspace["pipeline"] == "governance_candidate_review_workspace"
    assert workspace["summary"] == {
        "total_review_items": 2,
        "pending_review_items": 2,
        "requires_human_review": True,
        "by_owner_role": {"ontology_steward": 2},
        "by_recommended_decision": {"consider_modeling": 2},
        "by_derived_class": {
            "at_risk_equipment": 1,
            "high_value_material": 1,
        },
    }
    assert workspace["boundaries"] == {
        "offline_only": True,
        "writes_to_database": False,
        "creates_real_governance_issues": False,
        "applies_model_changes": False,
        "publishes_model_package": False,
        "requires_human_review": True,
    }

    item = workspace["review_items"][0]
    assert item["review_item_id"] == "gov-0001"
    assert item["source_record_identity"] == {
        "source": "rule_validation_report.json",
        "table": "equipment",
        "row": "7",
        "finding_id": "derived_class-0001",
        "rule_id": "derived_class",
    }
    assert item["affected_scope"] == {
        "source_table": "equipment",
        "derived_class": "at_risk_equipment",
        "candidate_group_size": 1,
    }
    assert item["decision_record"] == {
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
    }
    assert "source_path" not in json.dumps(workspace)
    assert "storage_path" not in json.dumps(workspace)


def test_write_review_workspace_outputs_json_and_markdown(tmp_path):
    mod = _load_module()
    _write_tiny_artifacts(tmp_path)
    json_path = tmp_path / "workspace.json"
    markdown_path = tmp_path / "workspace.md"

    workspace = mod.write_review_workspace(tmp_path, json_path, markdown_path)

    assert json.loads(json_path.read_text(encoding="utf-8")) == workspace
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "# Governance Candidate Review Workspace" in markdown
    assert "gov-0001" in markdown
    assert "at_risk_equipment" in markdown
    assert "Status remains `pending` until a human reviewer records a decision." in markdown
