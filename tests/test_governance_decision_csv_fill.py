"""Tests for explicit governance decision CSV filling."""

import csv
import importlib.util
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "fill_governance_decision_csv.py"


def _load_module():
    assert SCRIPT_PATH.is_file(), f"missing script: {SCRIPT_PATH.name}"
    spec = importlib.util.spec_from_file_location(
        "fill_governance_decision_csv", SCRIPT_PATH
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _rows() -> list[dict[str, str]]:
    base = {
        "decision": "",
        "reviewer": "",
        "reviewed_at": "",
        "rationale": "",
        "recommended_decision": "consider_modeling",
        "review_owner_role": "ontology_steward",
        "severity": "info",
        "finding_id": "derived_class-0001",
        "rule_id": "derived_class",
        "finding_message": "candidate",
        "required_checks": "confirm_business_meaning",
        "evidence_anchor": "",
    }
    return [
        {
            **base,
            "review_item_id": "gov-0001",
            "source_table": "equipment",
            "derived_class": "at_risk_equipment",
        },
        {
            **base,
            "review_item_id": "gov-0002",
            "source_table": "equipment",
            "derived_class": "at_risk_equipment",
        },
        {
            **base,
            "review_item_id": "gov-0003",
            "source_table": "materials",
            "derived_class": "high_value_material",
        },
    ]


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_fill_decision_csv_updates_only_matching_rows(tmp_path):
    mod = _load_module()
    csv_path = tmp_path / "decisions.csv"
    _write_csv(csv_path, _rows())

    result = mod.fill_governance_decision_csv(
        csv_path=csv_path,
        decision="accept",
        reviewer="ontology_steward",
        reviewed_at="2026-07-09T08:00:00+00:00",
        rationale="Accepted after human review.",
        source_table="equipment",
        derived_class="at_risk_equipment",
    )

    assert result["pipeline"] == "governance_decision_csv_fill"
    assert result["summary"] == {
        "total_rows": 3,
        "matched_rows": 2,
        "updated_rows": 2,
        "skipped_existing_decisions": 0,
        "writes_to_database": False,
        "creates_real_governance_issues": False,
    }
    rows = _read_csv(csv_path)
    assert rows[0]["decision"] == "accept"
    assert rows[0]["reviewer"] == "ontology_steward"
    assert rows[0]["rationale"] == "Accepted after human review."
    assert rows[1]["decision"] == "accept"
    assert rows[2]["decision"] == ""
    assert result["updated_review_item_ids"] == ["gov-0001", "gov-0002"]
    serialized = json.dumps(result)
    assert "source_path" not in serialized
    assert "storage_path" not in serialized


def test_fill_decision_csv_requires_explicit_filter(tmp_path):
    mod = _load_module()
    csv_path = tmp_path / "decisions.csv"
    _write_csv(csv_path, _rows())

    try:
        mod.fill_governance_decision_csv(
            csv_path=csv_path,
            decision="reject",
            reviewer="ontology_steward",
            reviewed_at="2026-07-09T08:00:00+00:00",
            rationale="Rejected after human review.",
        )
    except ValueError as exc:
        assert "at least one filter" in str(exc)
    else:
        raise AssertionError("expected missing filter to fail")


def test_fill_decision_csv_skips_existing_decisions_unless_overwrite(tmp_path):
    mod = _load_module()
    csv_path = tmp_path / "decisions.csv"
    rows = _rows()
    rows[0]["decision"] = "defer"
    rows[0]["reviewer"] = "alice"
    rows[0]["reviewed_at"] = "2026-07-09T07:00:00+00:00"
    rows[0]["rationale"] = "Already reviewed."
    _write_csv(csv_path, rows)

    result = mod.fill_governance_decision_csv(
        csv_path=csv_path,
        decision="accept",
        reviewer="ontology_steward",
        reviewed_at="2026-07-09T08:00:00+00:00",
        rationale="Accepted after human review.",
        review_item_ids=["gov-0001"],
    )

    assert result["summary"]["updated_rows"] == 0
    assert result["summary"]["skipped_existing_decisions"] == 1
    assert _read_csv(csv_path)[0]["decision"] == "defer"

    overwrite_result = mod.fill_governance_decision_csv(
        csv_path=csv_path,
        decision="accept",
        reviewer="ontology_steward",
        reviewed_at="2026-07-09T08:00:00+00:00",
        rationale="Accepted after explicit overwrite.",
        review_item_ids=["gov-0001"],
        overwrite=True,
    )

    assert overwrite_result["summary"]["updated_rows"] == 1
    assert _read_csv(csv_path)[0]["decision"] == "accept"
    assert _read_csv(csv_path)[0]["rationale"] == "Accepted after explicit overwrite."


def test_fill_decision_csv_rejects_invalid_decision_or_missing_file(tmp_path):
    mod = _load_module()
    csv_path = tmp_path / "decisions.csv"
    _write_csv(csv_path, _rows())

    try:
        mod.fill_governance_decision_csv(
            csv_path=csv_path,
            decision="approve",
            reviewer="ontology_steward",
            reviewed_at="2026-07-09T08:00:00+00:00",
            rationale="Invalid decision.",
            review_item_ids=["gov-0001"],
        )
    except ValueError as exc:
        assert "invalid decision" in str(exc)
    else:
        raise AssertionError("expected invalid decision to fail")

    try:
        mod.fill_governance_decision_csv(
            csv_path=tmp_path / "missing.csv",
            decision="reject",
            reviewer="ontology_steward",
            reviewed_at="2026-07-09T08:00:00+00:00",
            rationale="Missing file.",
            review_item_ids=["gov-0001"],
        )
    except FileNotFoundError as exc:
        assert "missing.csv not found" in str(exc)
    else:
        raise AssertionError("expected missing CSV to fail")
