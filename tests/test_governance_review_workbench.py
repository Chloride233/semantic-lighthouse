"""Tests for offline governance review workbench generation."""

import csv
import importlib.util
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "build_governance_review_workbench.py"


def _load_module():
    assert SCRIPT_PATH.is_file(), f"missing script: {SCRIPT_PATH.name}"
    spec = importlib.util.spec_from_file_location(
        "build_governance_review_workbench", SCRIPT_PATH
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _write_briefing(data_dir: Path) -> None:
    _write_json(
        data_dir / "governance_review_briefing.json",
        {
            "briefing_version": "1.0",
            "pipeline": "governance_review_briefing",
            "data_pack": {"path": str(data_dir)},
            "summary": {
                "total_review_items": 2,
                "group_count": 1,
                "pending_decision_items": 2,
                "completed_decision_items": 0,
                "groups_with_source_row_samples": 1,
                "requires_human_review": True,
            },
            "decision_options": [
                "accept",
                "reject",
                "defer",
                "needs_more_evidence",
            ],
            "review_groups": [
                {
                    "group_key": "equipment::at_risk_equipment",
                    "source_table": "equipment",
                    "derived_class": "at_risk_equipment",
                    "total_items": 2,
                    "pending_decision_items": 2,
                    "completed_decision_items": 0,
                    "review_item_ids": ["gov-0001", "gov-0002"],
                    "pending_review_item_ids": ["gov-0001", "gov-0002"],
                    "owner_roles": ["ontology_steward"],
                    "required_checks": [
                        "confirm_business_meaning",
                        "confirm_not_hard_relation",
                    ],
                    "finding_messages": [
                        "Equipment with degraded or down status requiring attention"
                    ],
                    "source_row_samples": [
                        {
                            "review_item_id": "gov-0001",
                            "table": "equipment",
                            "row": "1",
                            "values": {
                                "equipment_id": "EQP-1",
                                "equipment_name": "CNC Asset",
                                "status": "degraded",
                                "source_path": "C:/unsafe/raw.csv",
                            },
                        }
                    ],
                }
            ],
            "boundaries": {
                "offline_only": True,
                "writes_to_database": False,
                "creates_real_governance_issues": False,
                "applies_model_changes": False,
                "publishes_model_package": False,
                "executes_runtime_query": False,
                "briefing_only": True,
                "auto_accepts_candidates": False,
                "requires_explicit_human_decision": True,
            },
        },
    )


def _write_decision_csv(path: Path) -> None:
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
            "evidence_anchor": '{"source":"rule_validation_report.json"}',
        },
        {
            "review_item_id": "gov-0002",
            "decision": "defer",
            "reviewer": "alice",
            "reviewed_at": "2026-07-09T08:00:00+00:00",
            "rationale": "Needs domain owner review.",
            "recommended_decision": "consider_modeling",
            "review_owner_role": "ontology_steward",
            "severity": "info",
            "source_table": "equipment",
            "derived_class": "at_risk_equipment",
            "finding_id": "derived_class-0002",
            "rule_id": "derived_class",
            "finding_message": "Equipment classified as at_risk_equipment",
            "required_checks": "confirm_business_meaning",
            "evidence_anchor": '{"source":"rule_validation_report.json"}',
        },
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def test_build_workbench_embeds_review_data_and_boundaries(tmp_path):
    mod = _load_module()
    _write_briefing(tmp_path)
    csv_path = tmp_path / "governance_review_decisions_template.csv"
    _write_decision_csv(csv_path)

    result = mod.build_governance_review_workbench(tmp_path, csv_path)

    assert result["workbench_version"] == "1.0"
    assert result["pipeline"] == "governance_review_workbench"
    assert result["source_artifacts"]["governance_review_briefing"] == str(
        tmp_path / "governance_review_briefing.json"
    )
    assert result["summary"] == {
        "review_groups": 1,
        "decision_rows": 2,
        "pending_decision_rows": 1,
        "completed_decision_rows": 1,
        "requires_human_review": True,
    }
    assert result["boundaries"] == {
        "offline_only": True,
        "writes_to_database": False,
        "creates_real_governance_issues": False,
        "applies_model_changes": False,
        "publishes_model_package": False,
        "executes_runtime_query": False,
        "workbench_only": True,
        "auto_accepts_candidates": False,
        "requires_explicit_human_decision": True,
    }
    serialized = json.dumps(result)
    assert "source_path" not in serialized
    assert "C:/unsafe" not in serialized


def test_write_workbench_outputs_static_html(tmp_path):
    mod = _load_module()
    _write_briefing(tmp_path)
    csv_path = tmp_path / "governance_review_decisions_template.csv"
    _write_decision_csv(csv_path)
    output = tmp_path / "governance_review_workbench.html"

    result = mod.write_governance_review_workbench(tmp_path, csv_path, output)

    assert result["source_artifacts"]["workbench_html"] == str(output)
    html = output.read_text(encoding="utf-8")
    assert "<title>Governance Review Workbench</title>" in html
    assert "equipment / at_risk_equipment" in html
    assert "CNC Asset" in html
    assert "data-review-workbench" in html
    assert "downloadCsv" in html
    assert "accept" in html
    assert "needs_more_evidence" in html
    assert "source_path" not in html
    assert "C:/unsafe" not in html
    assert "writesToDatabase: false" in html
    assert "autoAcceptsCandidates: false" in html


def test_workbench_includes_group_decision_controls(tmp_path):
    mod = _load_module()
    _write_briefing(tmp_path)
    csv_path = tmp_path / "governance_review_decisions_template.csv"
    _write_decision_csv(csv_path)
    output = tmp_path / "governance_review_workbench.html"

    mod.write_governance_review_workbench(tmp_path, csv_path, output)

    html = output.read_text(encoding="utf-8")
    assert "Batch decision" in html
    assert "id=\"group-decision\"" in html
    assert "id=\"group-reviewer\"" in html
    assert "id=\"group-reviewed-at\"" in html
    assert "id=\"group-rationale\"" in html
    assert "id=\"apply-group\"" in html
    assert "applyGroupDecision" in html
    assert "existing decisions are preserved" in html
    assert "source_path" not in html
    assert "C:/unsafe" not in html


def test_missing_briefing_fails_clearly(tmp_path):
    mod = _load_module()

    try:
        mod.build_governance_review_workbench(tmp_path)
    except FileNotFoundError as exc:
        assert "governance_review_briefing.json not found" in str(exc)
    else:
        raise AssertionError("expected missing briefing to fail")
