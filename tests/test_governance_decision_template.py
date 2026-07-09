"""Tests for offline governance review decision template generation."""

import importlib.util
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "build_governance_decision_template.py"


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "build_governance_decision_template", SCRIPT_PATH
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
            "pipeline": "governance_candidate_review_workspace",
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


def test_build_decision_template_preserves_pending_human_input(tmp_path):
    mod = _load_module()
    _write_workspace(tmp_path)

    result = mod.build_governance_decision_template(tmp_path)

    assert result["template_version"] == "1.0"
    assert result["pipeline"] == "governance_review_decision_template"
    assert result["summary"] == {
        "total_template_decisions": 2,
        "open_decisions": 2,
        "ready_for_apply": False,
        "requires_human_review": True,
        "writes_to_database": False,
        "creates_real_governance_issues": False,
    }
    assert result["instructions"] == {
        "target_decision_file": "governance_review_decisions.json",
        "copy_template_before_filling": True,
        "required_fields": [
            "review_item_id",
            "decision",
            "reviewer",
            "reviewed_at",
            "rationale",
        ],
        "allowed_decisions": [
            "accept",
            "reject",
            "defer",
            "needs_more_evidence",
        ],
        "apply_command": (
            ".\\.venv\\Scripts\\python scripts\\apply_governance_review_decisions.py "
            "--data-pack <data-pack>"
        ),
    }
    assert result["decisions"][0] == {
        "review_item_id": "gov-0001",
        "template_status": "needs_human_input",
        "candidate": {
            "severity": "info",
            "candidate_types": ["ontology_modeling_opportunity"],
            "recommended_decision": "consider_modeling",
            "review_owner_role": "ontology_steward",
        },
        "affected_scope": {
            "source_table": "equipment",
            "derived_class": "at_risk_equipment",
            "candidate_group_size": 1,
        },
        "finding": {
            "finding_id": "derived_class-0001",
            "rule_id": "derived_class",
            "table": "equipment",
            "message": "Equipment classified as at_risk_equipment",
        },
        "required_checks": [
            "confirm_business_meaning",
            "confirm_not_hard_relation",
        ],
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
        "decision": None,
        "reviewer": None,
        "reviewed_at": None,
        "rationale": None,
    }
    assert result["boundaries"] == {
        "offline_only": True,
        "writes_to_database": False,
        "creates_real_governance_issues": False,
        "applies_model_changes": False,
        "publishes_model_package": False,
        "hard_reasoning_allowed": False,
        "requires_human_review": True,
        "auto_accepts_candidates": False,
    }
    serialized = json.dumps(result)
    assert "source_path" not in serialized
    assert "storage_path" not in serialized


def test_missing_review_workspace_fails_clearly(tmp_path):
    mod = _load_module()

    try:
        mod.build_governance_decision_template(tmp_path)
    except FileNotFoundError as exc:
        assert "governance_review_workspace.json not found" in str(exc)
    else:
        raise AssertionError("expected missing workspace to fail")


def test_write_decision_template_outputs_json_and_markdown(tmp_path):
    mod = _load_module()
    _write_workspace(tmp_path)
    json_path = tmp_path / "template.json"
    markdown_path = tmp_path / "template.md"

    result = mod.write_governance_decision_template(
        tmp_path,
        json_path,
        markdown_path,
    )

    assert json.loads(json_path.read_text(encoding="utf-8")) == result
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "# Governance Review Decision Template" in markdown
    assert "Ready for apply: `false`" in markdown
    assert "gov-0001" in markdown
    assert "Writes to database: `false`" in markdown
