"""Tests for offline governance review decision CSV workflow."""

import csv
import importlib.util
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BUILD_SCRIPT_PATH = REPO_ROOT / "scripts" / "build_governance_decision_csv.py"
CONVERT_SCRIPT_PATH = REPO_ROOT / "scripts" / "convert_governance_decision_csv.py"


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
                        "required_checks": [
                            "confirm_business_meaning",
                            "confirm_not_hard_relation",
                        ],
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
                },
                {
                    "review_item_id": "gov-0002",
                    "candidate": {
                        "severity": "warning",
                        "recommended_decision": "needs_more_evidence",
                        "review_owner_role": "data_steward",
                    },
                    "finding": {
                        "finding_id": "fk-0002",
                        "rule_id": "foreign_key_candidate",
                        "table": "materials",
                        "message": "Material relationship needs review",
                    },
                    "affected_scope": {
                        "source_table": "materials",
                        "derived_class": "",
                    },
                    "review_requirements": {
                        "required_checks": ["confirm_source_system_owner"],
                    },
                    "evidence_anchors": [
                        {
                            "source": "rule_validation_report.json",
                            "finding_id": "fk-0002",
                            "rule_id": "foreign_key_candidate",
                            "table": "materials",
                            "row": "11",
                            "source_path": "C:/unsafe/raw/source.csv",
                        }
                    ],
                },
            ],
        },
    )


def test_write_decision_csv_template_is_human_fillable_and_safe(tmp_path):
    mod = _load_module("build_governance_decision_csv", BUILD_SCRIPT_PATH)
    _write_workspace(tmp_path)
    csv_path = tmp_path / "governance_review_decisions_template.csv"

    rows = mod.write_governance_decision_csv(tmp_path, csv_path)

    assert csv_path.is_file()
    written_rows = list(csv.DictReader(csv_path.open(encoding="utf-8", newline="")))
    assert written_rows == rows
    assert written_rows[0] == {
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
        "required_checks": (
            "confirm_business_meaning;confirm_not_hard_relation"
        ),
        "evidence_anchor": (
            '{"column": null, "derived_class": "at_risk_equipment", '
            '"finding_id": "derived_class-0001", "row": "7", '
            '"rule_id": "derived_class", '
            '"source": "rule_validation_report.json", "table": "equipment"}'
        ),
    }
    serialized = json.dumps(written_rows)
    assert "source_path" not in serialized
    assert "storage_path" not in serialized
    assert "C:/unsafe" not in serialized


def test_convert_filled_decision_csv_to_json_skips_blank_rows(tmp_path):
    build_mod = _load_module("build_governance_decision_csv", BUILD_SCRIPT_PATH)
    convert_mod = _load_module(
        "convert_governance_decision_csv", CONVERT_SCRIPT_PATH
    )
    _write_workspace(tmp_path)
    csv_path = tmp_path / "governance_review_decisions_template.csv"
    rows = build_mod.write_governance_decision_csv(tmp_path, csv_path)
    rows[0]["decision"] = "accept"
    rows[0]["reviewer"] = "alice"
    rows[0]["reviewed_at"] = "2026-07-09T08:00:00+00:00"
    rows[0]["rationale"] = "Accepted for offline draft generation."
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=build_mod.CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    output_path = tmp_path / "governance_review_decisions.json"
    result = convert_mod.convert_governance_decision_csv(
        csv_path,
        output_path,
        review_batch="pilot-review",
    )

    assert json.loads(output_path.read_text(encoding="utf-8")) == result
    assert result["decision_version"] == "1.0"
    assert result["pipeline"] == "governance_review_decision_csv"
    assert result["review_batch"] == "pilot-review"
    assert result["summary"] == {
        "submitted_decisions": 1,
        "skipped_blank_rows": 1,
        "writes_to_database": False,
        "creates_real_governance_issues": False,
    }
    assert result["decisions"] == [
        {
            "review_item_id": "gov-0001",
            "decision": "accept",
            "reviewer": "alice",
            "reviewed_at": "2026-07-09T08:00:00+00:00",
            "rationale": "Accepted for offline draft generation.",
        }
    ]
    assert result["boundaries"]["offline_only"] is True
    assert result["boundaries"]["auto_accepts_candidates"] is False


def test_missing_workspace_or_csv_fails_clearly(tmp_path):
    build_mod = _load_module("build_governance_decision_csv", BUILD_SCRIPT_PATH)
    convert_mod = _load_module(
        "convert_governance_decision_csv", CONVERT_SCRIPT_PATH
    )

    try:
        build_mod.build_governance_decision_csv(tmp_path)
    except FileNotFoundError as exc:
        assert "governance_review_workspace.json not found" in str(exc)
    else:
        raise AssertionError("expected missing workspace to fail")

    try:
        convert_mod.convert_governance_decision_csv(
            tmp_path / "missing.csv",
            tmp_path / "governance_review_decisions.json",
        )
    except FileNotFoundError as exc:
        assert "missing.csv not found" in str(exc)
    else:
        raise AssertionError("expected missing CSV to fail")
