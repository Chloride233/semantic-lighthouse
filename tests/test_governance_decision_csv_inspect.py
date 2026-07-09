"""Tests for governance decision CSV completion inspection."""

import csv
import importlib.util
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "inspect_governance_decision_csv.py"


def _load_module():
    assert SCRIPT_PATH.is_file(), f"missing script: {SCRIPT_PATH.name}"
    spec = importlib.util.spec_from_file_location(
        "inspect_governance_decision_csv", SCRIPT_PATH
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _base_row() -> dict[str, str]:
    return {
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
        "evidence_anchor": '{"source": "rule_validation_report.json"}',
    }


def test_complete_decision_csv_passes_inspection(tmp_path):
    mod = _load_module()
    csv_path = tmp_path / "governance_review_decisions_template.csv"
    _write_csv(csv_path, [_base_row()])

    result = mod.inspect_governance_decision_csv(csv_path)

    assert result["inspection_version"] == "1.0"
    assert result["pipeline"] == "governance_decision_csv_inspection"
    assert result["summary"] == {
        "inspection_status": "PASS",
        "total_rows": 1,
        "complete_rows": 1,
        "blank_decision_rows": 0,
        "incomplete_rows": 0,
        "error_count": 0,
        "ready_for_post_review_runner": True,
    }
    assert result["findings"] == []
    assert result["boundaries"] == {
        "offline_only": True,
        "writes_to_database": False,
        "creates_real_governance_issues": False,
        "applies_model_changes": False,
        "publishes_model_package": False,
        "executes_runtime_query": False,
        "inspection_only": True,
    }


def test_incomplete_decision_csv_reports_missing_fields(tmp_path):
    mod = _load_module()
    csv_path = tmp_path / "governance_review_decisions_template.csv"
    blank_row = _base_row()
    blank_row["review_item_id"] = "gov-0002"
    blank_row["decision"] = ""
    blank_row["source_path"] = "C:/unsafe/raw.csv"
    missing_reviewer = _base_row()
    missing_reviewer["review_item_id"] = "gov-0003"
    missing_reviewer["reviewer"] = ""
    missing_reviewer["rationale"] = ""
    _write_csv(csv_path, [blank_row, missing_reviewer])

    result = mod.inspect_governance_decision_csv(csv_path)

    assert result["summary"] == {
        "inspection_status": "REVIEW_INCOMPLETE",
        "total_rows": 2,
        "complete_rows": 0,
        "blank_decision_rows": 1,
        "incomplete_rows": 1,
        "error_count": 3,
        "ready_for_post_review_runner": False,
    }
    assert result["findings"] == [
        {
            "severity": "ERROR",
            "code": "blank_decision",
            "row_number": 2,
            "review_item_id": "gov-0002",
            "message": "decision is required before post-review runner.",
        },
        {
            "severity": "ERROR",
            "code": "missing_reviewer",
            "row_number": 3,
            "review_item_id": "gov-0003",
            "message": "reviewer is required when decision is set.",
        },
        {
            "severity": "ERROR",
            "code": "missing_rationale",
            "row_number": 3,
            "review_item_id": "gov-0003",
            "message": "rationale is required when decision is set.",
        },
    ]
    serialized = json.dumps(result)
    assert "source_path" not in serialized
    assert "C:/unsafe" not in serialized


def test_write_inspection_outputs_json_and_markdown(tmp_path):
    mod = _load_module()
    csv_path = tmp_path / "decisions.csv"
    _write_csv(csv_path, [_base_row()])
    json_path = tmp_path / "inspection.json"
    markdown_path = tmp_path / "inspection.md"

    result = mod.write_governance_decision_csv_inspection(
        csv_path,
        json_path,
        markdown_path,
    )

    assert json.loads(json_path.read_text(encoding="utf-8")) == result
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "# Governance Decision CSV Inspection" in markdown
    assert "Inspection status: `PASS`" in markdown
    assert "Ready for post-review runner: `true`" in markdown


def test_missing_decision_csv_fails_clearly(tmp_path):
    mod = _load_module()

    try:
        mod.inspect_governance_decision_csv(tmp_path / "missing.csv")
    except FileNotFoundError as exc:
        assert "missing.csv not found" in str(exc)
    else:
        raise AssertionError("expected missing CSV to fail")
