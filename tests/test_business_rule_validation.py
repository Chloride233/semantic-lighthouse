"""Tests for Phase 19.4 business rule validation.

Covers:
  - Clean data pack produces well-formed rule_validation_report.json
  - required_field null violations detected
  - pk_unique duplication detected
  - fk_integrity broken FK detected
  - enum_allowed invalid values detected
  - date_order anomalies detected
  - derived_class identifies entities (INFO level)
"""

from __future__ import annotations

import csv
import json
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GEN_SCRIPT = REPO_ROOT / "scripts" / "generate_manufacturing_dataset.py"
MAP_GEN = REPO_ROOT / "scripts" / "generate_mapping_contract.py"
RULE_VAL = REPO_ROOT / "scripts" / "validate_business_rules.py"


# ── Helpers ──────────────────────────────────────────────────────────────────

def _run(script: Path, args: list[str], timeout: int = 30) -> tuple[int, str]:
    import subprocess
    import sys
    result = subprocess.run(
        [sys.executable, str(script)] + args,
        capture_output=True, text=True, timeout=timeout,
    )
    return result.returncode, result.stdout


def setup_data_pack(tmp_dir: Path, preset: str = "tiny", seed: int = 42) -> Path:
    """Generate a full data pack with manifest + mapping_contract."""
    out = tmp_dir / "data"
    rc, _ = _run(GEN_SCRIPT, [
        "--preset", preset, "--seed", str(seed), "--output-dir", str(out),
    ])
    assert rc == 0, "Generator failed"
    rc, _ = _run(MAP_GEN, ["--data-pack", str(out)])
    assert rc == 0, "Mapping contract generator failed"
    return out


def run_rules(data_dir: Path, fail_on_warn: bool = False) -> tuple[int, str]:
    """Run the business rule validator."""
    cmd = ["--data-pack", str(data_dir)]
    if fail_on_warn:
        cmd.append("--fail-on-warn")
    return _run(RULE_VAL, cmd, timeout=15)


def load_report(data_dir: Path) -> dict:
    """Load rule_validation_report.json."""
    return json.loads(
        (data_dir / "rule_validation_report.json").read_text(encoding="utf-8")
    )


def get_rule(report: dict, rule_id: str) -> dict:
    """Get a specific rule result from the report."""
    for r in report["rule_results"]:
        if r["rule_id"] == rule_id:
            return r
    return {}


# ── Tests ────────────────────────────────────────────────────────────────────


class TestBusinessRuleValidation:
    """Verify the rule validation engine (Phase 19.4)."""

    def test_clean_data_generates_report_with_correct_schema(self):
        """Report is well-formed with all required sections even if some
        rules find genuine anomalies in synthetic data."""
        with tempfile.TemporaryDirectory() as tmp:
            out = setup_data_pack(Path(tmp))
            exit_code, output = run_rules(out)
            report = load_report(out)

            # Top-level schema
            assert report["report_version"] == "1.0"
            assert "generated_at" in report
            assert report["data_pack"] == "manufacturing"
            assert report["source_manifest"] == "manifest.json"
            assert report["source_mapping_contract"] == "mapping_contract.json"

            # Summary
            s = report["summary"]
            assert s["total_rules"] == 8
            assert "rules_passed" in s
            assert "rules_failed" in s
            assert "total_checks" in s
            assert "total_findings" in s

            # Boundaries
            b = report["boundaries"]
            assert b["offline_only"] is True
            assert b["writes_to_database"] is False
            assert b["creates_governance_issues"] is False

            # Rule results have correct structure
            rule_ids = {r["rule_id"] for r in report["rule_results"]}
            expected_rules = {
                "required_field", "pk_unique", "fk_integrity",
                "enum_allowed", "numeric_range", "date_order",
                "derived_class", "row_count_range",
            }
            assert rule_ids == expected_rules

            # Each rule result has required fields
            for r in report["rule_results"]:
                for field in ("rule_id", "rule_name", "status",
                              "checks_performed", "findings"):
                    assert field in r, (
                        f"Rule '{r.get('rule_id', '?')}' missing '{field}'"
                    )
                assert isinstance(r["findings"], list)

            # Findings have required fields
            for f_obj in report["findings"]:
                for field in ("rule_id", "status", "finding_id", "table",
                              "message", "evidence"):
                    assert field in f_obj, (
                        f"Finding '{f_obj.get('finding_id', '?')}' "
                        f"missing '{field}'"
                    )

            # Derived class should identify entities
            dc = get_rule(report, "derived_class")
            assert dc["status"] == "PASS"
            classified = dc.get("entities_classified", 0)
            assert classified >= 1, (
                f"Expected at least 1 derived entity, got {classified}"
            )

            # Row count range should pass
            rc_rule = get_rule(report, "row_count_range")
            assert rc_rule["status"] == "PASS"

    def test_required_field_null_detected(self):
        """Null value in a forbid column produces a FAIL finding."""
        with tempfile.TemporaryDirectory() as tmp:
            out = setup_data_pack(Path(tmp))
            # Corrupt: null out supplier_name
            csv_path = out / "suppliers.csv"
            rows = _read_and_modify_csv(csv_path, "supplier_name",
                                        lambda v: "")
            _rewrite_csv(csv_path, rows)

            exit_code, _ = run_rules(out)
            assert exit_code == 1
            report = load_report(out)
            rf = get_rule(report, "required_field")
            assert rf["status"] == "FAIL"
            assert rf["violations_found"] >= 1
            # Verify finding structure
            f_obj = rf["findings"][0]
            assert f_obj["rule_id"] == "required_field"
            assert f_obj["table"] == "suppliers"
            assert f_obj["column"] == "supplier_name"

    def test_pk_unique_duplicate_detected(self):
        """Duplicate primary key produces a FAIL finding."""
        with tempfile.TemporaryDirectory() as tmp:
            out = setup_data_pack(Path(tmp))
            csv_path = out / "materials.csv"
            rows = _read_csv_rows(csv_path)
            if len(rows) >= 2:
                rows[0]["material_id"] = rows[1]["material_id"]
                _rewrite_csv(csv_path, rows)

            exit_code, _ = run_rules(out)
            assert exit_code == 1
            report = load_report(out)
            pk = get_rule(report, "pk_unique")
            assert pk["status"] == "FAIL"
            assert pk["violations_found"] >= 1
            f_obj = pk["findings"][0]
            assert f_obj["table"] == "materials"

    def test_fk_integrity_broken_detected(self):
        """Broken foreign key produces a FAIL finding."""
        with tempfile.TemporaryDirectory() as tmp:
            out = setup_data_pack(Path(tmp))
            # Truncate suppliers so materials FK breaks
            csv_path = out / "suppliers.csv"
            rows = _read_csv_rows(csv_path)
            if len(rows) > 1:
                _rewrite_csv(csv_path, rows[-1:])  # keep only last

            exit_code, _ = run_rules(out)
            assert exit_code == 1
            report = load_report(out)
            fk = get_rule(report, "fk_integrity")
            assert fk["status"] == "FAIL"
            assert fk["violations_found"] >= 1
            f_obj = fk["findings"][0]
            assert f_obj["table"] == "materials"

    def test_enum_allowed_invalid_value_detected(self):
        """Invalid enum value produces a FAIL finding."""
        with tempfile.TemporaryDirectory() as tmp:
            out = setup_data_pack(Path(tmp))
            csv_path = out / "suppliers.csv"
            rows = _read_and_modify_csv(csv_path, "country",
                                        lambda v: "XX")
            _rewrite_csv(csv_path, rows)

            exit_code, _ = run_rules(out)
            assert exit_code == 1
            report = load_report(out)
            en = get_rule(report, "enum_allowed")
            assert en["status"] == "FAIL"
            assert en["violations_found"] >= 1
            f_obj = en["findings"][0]
            assert f_obj["column"] == "country"
            assert "XX" in f_obj["message"]

    def test_date_order_anomaly_detected(self):
        """Date order rule catches start > end in synthetic data."""
        with tempfile.TemporaryDirectory() as tmp:
            out = setup_data_pack(Path(tmp))
            run_rules(out)
            report = load_report(out)
            do = get_rule(report, "date_order")
            # Synthetic data generator produces some out-of-order dates
            assert do["status"] in ("FAIL", "WARN"), (
                f"Expected date_order to find anomalies, got {do['status']}"
            )
            if do["violations_found"] > 0:
                f_obj = do["findings"][0]
                assert f_obj["table"] in (
                    "work_orders", "work_order_operations",
                    "equipment_maintenance",
                )

    def test_derived_class_identifies_entities(self):
        """Derived class rule identifies entities with INFO status."""
        with tempfile.TemporaryDirectory() as tmp:
            out = setup_data_pack(Path(tmp))
            run_rules(out)
            report = load_report(out)
            dc = get_rule(report, "derived_class")
            assert dc["status"] == "PASS"  # INFO never causes FAIL
            classified = dc.get("entities_classified", 0)
            assert classified >= 1
            # Each finding is INFO, not FAIL
            for f_obj in dc["findings"]:
                assert f_obj["status"] == "INFO"


# ── Low-level CSV helpers ────────────────────────────────────────────────────

def _read_csv_rows(csv_path: Path) -> list[dict[str, str]]:
    with open(csv_path, "r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _read_and_modify_csv(
    csv_path: Path, column: str, modifier,
) -> list[dict[str, str]]:
    """Read CSV and apply modifier to a column in all rows."""
    rows = _read_csv_rows(csv_path)
    for row in rows:
        row[column] = modifier(row.get(column, ""))
    return rows


def _rewrite_csv(csv_path: Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        return
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
