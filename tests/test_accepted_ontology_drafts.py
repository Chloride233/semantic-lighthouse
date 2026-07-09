"""Tests for building offline ontology drafts from accepted governance changes."""

import importlib.util
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "build_accepted_ontology_drafts.py"


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "build_accepted_ontology_drafts", SCRIPT_PATH
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _write_accepted_changes(data_dir: Path, changes: list[dict]) -> None:
    _write_json(
        data_dir / "accepted_governance_changes.json",
        {
            "change_version": "1.0",
            "pipeline": "governance_review_decisions",
            "data_pack": {"path": str(data_dir)},
            "summary": {
                "workspace_items": 2,
                "submitted_decisions": len(changes),
                "accepted_decisions": len(changes),
                "accepted_change_count": len(changes),
                "undecided_items": 2 - len(changes),
            },
            "accepted_changes": changes,
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


def _accepted_change() -> dict:
    return {
        "change_id": "accepted-gov-0001",
        "source_review_item_id": "gov-0001",
        "status": "accepted_for_draft",
        "change_type": "derived_class_candidate",
        "target": {
            "source_table": "equipment",
            "derived_class": "at_risk_equipment",
        },
        "finding": {
            "finding_id": "derived_class-0001",
            "rule_id": "derived_class",
            "table": "equipment",
            "message": "Equipment classified as at_risk_equipment",
        },
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
        "review": {
            "decision": "accept",
            "reviewer": "alice",
            "reviewed_at": "2026-07-09T08:00:00+00:00",
            "rationale": "Useful pilot class.",
        },
        "rollback_note": "Keep as offline unless accepted.",
        "hard_reasoning_allowed": False,
    }


def test_build_accepted_ontology_drafts_from_accepted_changes(tmp_path):
    mod = _load_module()
    _write_accepted_changes(tmp_path, [_accepted_change()])

    result = mod.build_accepted_ontology_drafts(tmp_path)

    assert result["draft_artifact_version"] == "1.0"
    assert result["pipeline"] == "accepted_ontology_drafts"
    assert result["summary"] == {
        "accepted_change_count": 1,
        "draft_count": 1,
        "derived_class_draft_count": 1,
        "hard_reasoning_allowed": False,
        "publishes_model_package": False,
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

    draft = result["drafts"][0]
    assert draft["draft_id"] == "offline-draft-accepted-gov-0001"
    assert draft["draft_type"] == "derived_class"
    assert draft["status"] == "accepted"
    assert draft["name"] == "at_risk_equipment"
    assert draft["description"] == "Accepted derived class candidate for equipment."
    assert draft["source_change_id"] == "accepted-gov-0001"
    assert draft["source_review_item_id"] == "gov-0001"
    assert draft["source_table"] == "equipment"
    assert draft["payload"] == {
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
    }
    assert draft["review"] == {
        "decision": "accept",
        "reviewer": "alice",
        "reviewed_at": "2026-07-09T08:00:00+00:00",
        "rationale": "Useful pilot class.",
    }
    assert draft["evidence_refs"] == [
        {
            "source": "rule_validation_report.json",
            "finding_id": "derived_class-0001",
            "rule_id": "derived_class",
            "table": "equipment",
            "row": "7",
            "column": None,
            "derived_class": "at_risk_equipment",
        }
    ]
    assert "source_path" not in json.dumps(result)
    assert "storage_path" not in json.dumps(result)


def test_empty_accepted_changes_outputs_empty_drafts(tmp_path):
    mod = _load_module()
    _write_accepted_changes(tmp_path, [])

    result = mod.build_accepted_ontology_drafts(tmp_path)

    assert result["summary"]["accepted_change_count"] == 0
    assert result["summary"]["draft_count"] == 0
    assert result["drafts"] == []
    assert result["boundaries"]["publishes_model_package"] is False


def test_write_accepted_ontology_drafts_outputs_json_and_markdown(tmp_path):
    mod = _load_module()
    _write_accepted_changes(tmp_path, [_accepted_change()])
    json_path = tmp_path / "drafts.json"
    markdown_path = tmp_path / "drafts.md"

    result = mod.write_accepted_ontology_drafts(tmp_path, json_path, markdown_path)

    assert json.loads(json_path.read_text(encoding="utf-8")) == result
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "# Accepted Ontology Drafts" in markdown
    assert "offline-draft-accepted-gov-0001" in markdown
    assert "at_risk_equipment" in markdown
    assert "Publishes model package: `false`" in markdown
