"""Tests for offline model package bridge generation."""

import importlib.util
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "build_offline_model_package.py"


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "build_offline_model_package", SCRIPT_PATH
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _draft() -> dict:
    return {
        "draft_id": "offline-draft-accepted-gov-0001",
        "draft_type": "derived_class",
        "status": "accepted",
        "name": "at_risk_equipment",
        "description": "Accepted derived class candidate for equipment.",
        "source_change_id": "accepted-gov-0001",
        "source_review_item_id": "gov-0001",
        "source_table": "equipment",
        "payload": {
            "generator": "governance_review_decisions_v1",
            "generation_key": "derived_class:equipment:at_risk_equipment",
            "source_table": "equipment",
            "derived_class": "at_risk_equipment",
            "classification_rule": {
                "rule_id": "derived_class",
                "finding_id": "derived_class-0001",
                "message": "Equipment classified as at_risk_equipment",
            },
            "hard_reasoning_allowed": False,
        },
        "evidence_refs": [
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
        "review": {
            "decision": "accept",
            "reviewer": "alice",
            "reviewed_at": "2026-07-09T08:00:00+00:00",
            "rationale": "Useful pilot class.",
        },
        "rollback_note": "Keep as offline unless accepted.",
        "hard_reasoning_allowed": False,
    }


def _write_drafts(data_dir: Path, drafts: list[dict]) -> None:
    _write_json(
        data_dir / "accepted_ontology_drafts.json",
        {
            "draft_artifact_version": "1.0",
            "pipeline": "accepted_ontology_drafts",
            "data_pack": {"path": str(data_dir)},
            "summary": {
                "accepted_change_count": len(drafts),
                "draft_count": len(drafts),
                "derived_class_draft_count": len(drafts),
                "hard_reasoning_allowed": False,
                "publishes_model_package": False,
            },
            "drafts": drafts,
            "boundaries": {
                "offline_only": True,
                "writes_to_database": False,
                "creates_real_governance_issues": False,
                "applies_model_changes": False,
                "publishes_model_package": False,
                "hard_reasoning_allowed": False,
                "requires_human_review": True,
            },
        },
    )


def test_build_offline_model_package_from_accepted_drafts(tmp_path):
    mod = _load_module()
    _write_drafts(tmp_path, [_draft()])

    result = mod.build_offline_model_package(tmp_path)

    assert result["package_artifact_version"] == "1.0"
    assert result["pipeline"] == "offline_model_package_bridge"
    assert result["summary"] == {
        "package_status": "BUILT",
        "draft_count": 1,
        "derived_class_count": 1,
        "source_draft_count": 1,
        "hard_reasoning_allowed": False,
        "writes_to_database": False,
    }
    assert result["boundaries"] == {
        "offline_only": True,
        "writes_to_database": False,
        "creates_real_governance_issues": False,
        "applies_model_changes": False,
        "publishes_model_package": False,
        "activates_runtime": False,
        "hard_reasoning_allowed": False,
        "requires_human_review": True,
    }

    package = result["model_package"]
    assert package["schema_version"] == "1.0"
    assert package["package_status"] == "offline_built"
    assert package["semantic_hash"].startswith("sha256:")
    assert len(package["semantic_hash"]) == 71
    assert package["source_draft_ids"] == ["offline-draft-accepted-gov-0001"]
    assert package["contract"]["derived_classes"] == [
        {
            "id": "offline-draft-accepted-gov-0001",
            "name": "at_risk_equipment",
            "description": "Accepted derived class candidate for equipment.",
            "source_table": "equipment",
            "payload": {
                "generator": "governance_review_decisions_v1",
                "generation_key": "derived_class:equipment:at_risk_equipment",
                "source_table": "equipment",
                "derived_class": "at_risk_equipment",
                "classification_rule": {
                    "rule_id": "derived_class",
                    "finding_id": "derived_class-0001",
                    "message": "Equipment classified as at_risk_equipment",
                },
                "hard_reasoning_allowed": False,
            },
            "evidence_refs": [
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
            "review": {
                "decision": "accept",
                "reviewer": "alice",
                "reviewed_at": "2026-07-09T08:00:00+00:00",
                "rationale": "Useful pilot class.",
            },
            "hard_reasoning_allowed": False,
        }
    ]
    assert "source_path" not in json.dumps(result)
    assert "storage_path" not in json.dumps(result)


def test_no_accepted_drafts_outputs_no_package_report(tmp_path):
    mod = _load_module()
    _write_drafts(tmp_path, [])

    result = mod.build_offline_model_package(tmp_path)

    assert result["summary"]["package_status"] == "NO_ACCEPTED_DRAFTS"
    assert result["summary"]["draft_count"] == 0
    assert result["model_package"] is None
    assert result["boundaries"]["publishes_model_package"] is False


def test_write_offline_model_package_outputs_json_and_markdown(tmp_path):
    mod = _load_module()
    _write_drafts(tmp_path, [_draft()])
    json_path = tmp_path / "package.json"
    markdown_path = tmp_path / "package.md"

    result = mod.write_offline_model_package(tmp_path, json_path, markdown_path)

    assert json.loads(json_path.read_text(encoding="utf-8")) == result
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "# Offline Model Package Bridge" in markdown
    assert "offline-draft-accepted-gov-0001" in markdown
    assert "at_risk_equipment" in markdown
    assert "Publishes model package: `false`" in markdown
