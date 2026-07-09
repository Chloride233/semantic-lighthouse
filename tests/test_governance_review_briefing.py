"""Tests for governance review briefing generation."""

import csv
import importlib.util
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "build_governance_review_briefing.py"


def _load_module():
    assert SCRIPT_PATH.is_file(), f"missing script: {SCRIPT_PATH.name}"
    spec = importlib.util.spec_from_file_location(
        "build_governance_review_briefing", SCRIPT_PATH
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _workspace_item(
    review_item_id: str,
    source_table: str,
    derived_class: str,
    row: str,
) -> dict:
    return {
        "review_item_id": review_item_id,
        "candidate": {
            "candidate_id": review_item_id,
            "severity": "info",
            "recommended_decision": "consider_modeling",
            "review_owner_role": "ontology_steward",
        },
        "finding": {
            "finding_id": f"derived_class-{review_item_id[-4:]}",
            "rule_id": "derived_class",
            "table": source_table,
            "message": f"Entity classified as {derived_class}",
        },
        "affected_scope": {
            "source_table": source_table,
            "derived_class": derived_class,
            "candidate_group_size": 2,
        },
        "review_requirements": {
            "requires_human_review": True,
            "required_checks": [
                "confirm_business_meaning",
                "confirm_not_hard_relation",
            ],
        },
        "evidence_anchors": [
            {
                "source": "rule_validation_report.json",
                "finding_id": f"derived_class-{review_item_id[-4:]}",
                "rule_id": "derived_class",
                "table": source_table,
                "row": row,
                "column": None,
                "derived_class": derived_class,
                "source_path": "C:/unsafe/raw.csv",
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
        },
    }


def _write_workspace(data_dir: Path) -> None:
    _write_json(
        data_dir / "governance_review_workspace.json",
        {
            "workspace_version": "1.0",
            "pipeline": "governance_candidate_review_workspace",
            "data_pack": {"path": str(data_dir)},
            "summary": {
                "total_review_items": 3,
                "pending_review_items": 3,
                "requires_human_review": True,
            },
            "review_items": [
                _workspace_item(
                    "gov-0001",
                    "equipment",
                    "at_risk_equipment",
                    "1",
                ),
                _workspace_item(
                    "gov-0002",
                    "equipment",
                    "at_risk_equipment",
                    "2",
                ),
                _workspace_item(
                    "gov-0003",
                    "materials",
                    "high_value_material",
                    "10",
                ),
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


def _write_csv(path: Path) -> None:
    rows = [
        {
            "review_item_id": "gov-0001",
            "decision": "",
            "reviewer": "",
            "reviewed_at": "",
            "rationale": "",
            "source_table": "equipment",
            "derived_class": "at_risk_equipment",
        },
        {
            "review_item_id": "gov-0002",
            "decision": "defer",
            "reviewer": "ontology_steward",
            "reviewed_at": "2026-07-09T08:00:00+00:00",
            "rationale": "Needs domain owner review.",
            "source_table": "equipment",
            "derived_class": "at_risk_equipment",
        },
        {
            "review_item_id": "gov-0003",
            "decision": "",
            "reviewer": "",
            "reviewed_at": "",
            "rationale": "",
            "source_table": "materials",
            "derived_class": "high_value_material",
        },
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def test_build_review_briefing_groups_pending_items_and_commands(tmp_path):
    mod = _load_module()
    _write_workspace(tmp_path)
    csv_path = tmp_path / "governance_review_decisions_template.csv"
    _write_csv(csv_path)

    result = mod.build_governance_review_briefing(tmp_path, csv_path)

    assert result["briefing_version"] == "1.0"
    assert result["pipeline"] == "governance_review_briefing"
    assert result["summary"] == {
        "total_review_items": 3,
        "group_count": 2,
        "pending_decision_items": 2,
        "completed_decision_items": 1,
        "requires_human_review": True,
    }
    assert result["decision_options"] == [
        "accept",
        "reject",
        "defer",
        "needs_more_evidence",
    ]

    equipment = result["review_groups"][0]
    assert equipment["group_key"] == "equipment::at_risk_equipment"
    assert equipment["source_table"] == "equipment"
    assert equipment["derived_class"] == "at_risk_equipment"
    assert equipment["total_items"] == 2
    assert equipment["pending_decision_items"] == 1
    assert equipment["completed_decision_items"] == 1
    assert equipment["review_item_ids"] == ["gov-0001", "gov-0002"]
    assert equipment["pending_review_item_ids"] == ["gov-0001"]
    assert equipment["required_checks"] == [
        "confirm_business_meaning",
        "confirm_not_hard_relation",
    ]
    assert "--source-table equipment" in equipment["fill_command_template"]
    assert "--derived-class at_risk_equipment" in equipment["fill_command_template"]
    assert "--decision <decision>" in equipment["fill_command_template"]
    assert "accept " not in equipment["fill_command_template"]

    serialized = json.dumps(result)
    assert "source_path" not in serialized
    assert "C:/unsafe" not in serialized
    assert result["boundaries"] == {
        "offline_only": True,
        "writes_to_database": False,
        "creates_real_governance_issues": False,
        "applies_model_changes": False,
        "publishes_model_package": False,
        "executes_runtime_query": False,
        "briefing_only": True,
        "auto_accepts_candidates": False,
        "requires_explicit_human_decision": True,
    }


def test_write_review_briefing_outputs_json_and_markdown(tmp_path):
    mod = _load_module()
    _write_workspace(tmp_path)
    csv_path = tmp_path / "governance_review_decisions_template.csv"
    _write_csv(csv_path)
    json_path = tmp_path / "briefing.json"
    markdown_path = tmp_path / "briefing.md"

    result = mod.write_governance_review_briefing(
        tmp_path,
        csv_path,
        json_path,
        markdown_path,
    )

    assert json.loads(json_path.read_text(encoding="utf-8")) == result
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "# Governance Review Briefing" in markdown
    assert "equipment" in markdown
    assert "at_risk_equipment" in markdown
    assert "--decision <decision>" in markdown
    assert "does not record decisions" in markdown


def test_missing_review_workspace_fails_clearly(tmp_path):
    mod = _load_module()

    try:
        mod.build_governance_review_briefing(tmp_path)
    except FileNotFoundError as exc:
        assert "governance_review_workspace.json not found" in str(exc)
    else:
        raise AssertionError("expected missing workspace to fail")
