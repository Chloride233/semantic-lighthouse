"""Tests for Semantic CI/CD Pipeline v1.

Covers the offline gate that orchestrates Phase 19 artifacts:
manifest -> mapping_contract -> rule_validation_report -> governance_feedback
-> semantic_ci_report.
"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GEN_SCRIPT = REPO_ROOT / "scripts" / "generate_manufacturing_dataset.py"
MAP_GEN = REPO_ROOT / "scripts" / "generate_mapping_contract.py"
SEMANTIC_CI = REPO_ROOT / "scripts" / "run_semantic_ci.py"


def _run(script: Path, args: list[str], timeout: int = 30) -> tuple[int, str]:
    result = subprocess.run(
        [sys.executable, str(script)] + args,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return result.returncode, result.stdout + result.stderr


def _generate_pack(out: Path) -> None:
    rc, output = _run(
        GEN_SCRIPT,
        ["--preset", "tiny", "--seed", "42", "--output-dir", str(out)],
    )
    assert rc == 0, output


def _generate_mapping(out: Path) -> None:
    rc, output = _run(MAP_GEN, ["--data-pack", str(out)])
    assert rc == 0, output


def _run_semantic_ci(
    out: Path,
    extra_args: list[str] | None = None,
) -> tuple[int, str]:
    args = ["--data-pack", str(out)]
    if extra_args:
        args.extend(extra_args)
    return _run(SEMANTIC_CI, args, timeout=30)


def _load_report(out: Path) -> dict:
    return json.loads((out / "semantic_ci_report.json").read_text(encoding="utf-8"))


def test_clean_tiny_pack_runs_full_pipeline_and_writes_report():
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "data"
        _generate_pack(out)

        rc, output = _run_semantic_ci(out)

        assert rc == 0, output
        report = _load_report(out)
        assert report["report_version"] == "1.0"
        assert report["pipeline"] == "semantic_ci"
        assert report["data_pack"]["preset"] == "tiny"
        assert report["data_pack"]["seed"] == 42
        assert report["data_pack"]["table_count"] == 13
        assert report["data_pack"]["total_rows"] == 279
        assert report["summary"]["gate_status"] in ("PASS", "WARN")
        assert report["summary"]["hard_failures"] == 0

        for gate_name in (
            "data_pack_contract",
            "mapping_contract",
            "business_rules",
            "governance_feedback",
        ):
            assert gate_name in report["gates"]
            assert report["gates"][gate_name]["status"] in ("PASS", "WARN")

        for artifact_name in (
            "manifest",
            "mapping_contract",
            "rule_validation_report",
            "governance_feedback",
        ):
            artifact = report["artifacts"][artifact_name]
            assert Path(artifact["path"]).is_file()
            assert artifact["sha256"]

        assert (out / "mapping_contract.json").is_file()
        assert (out / "rule_validation_report.json").is_file()
        assert (out / "governance_feedback.json").is_file()
        assert (out / "semantic_ci_report.json").is_file()


def test_missing_manifest_fails_data_pack_contract_gate():
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "data"
        out.mkdir()

        rc, output = _run_semantic_ci(out)

        assert rc == 1, output
        report = _load_report(out)
        assert report["summary"]["gate_status"] == "FAIL"
        assert report["summary"]["hard_failures"] == 1
        assert report["gates"]["data_pack_contract"]["status"] == "FAIL"
        assert "manifest.json not found" in report["gates"]["data_pack_contract"]["message"]


def test_corrupt_mapping_fails_and_regenerate_mapping_recovers():
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "data"
        _generate_pack(out)
        _generate_mapping(out)

        contract_path = out / "mapping_contract.json"
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        contract["object_type_mappings"][0]["column_mappings"][0][
            "source_column"
        ] = "nonexistent_column_xyz"
        contract_path.write_text(json.dumps(contract, indent=2), encoding="utf-8")

        rc, output = _run_semantic_ci(out)
        assert rc == 1, output
        report = _load_report(out)
        assert report["summary"]["gate_status"] == "FAIL"
        assert report["gates"]["mapping_contract"]["status"] == "FAIL"

        rc, output = _run_semantic_ci(out, ["--regenerate-mapping"])
        assert rc == 0, output
        report = _load_report(out)
        assert report["gates"]["mapping_contract"]["status"] == "PASS"
        repaired = json.loads(contract_path.read_text(encoding="utf-8"))
        first_col = repaired["object_type_mappings"][0]["column_mappings"][0]
        assert first_col["source_column"] != "nonexistent_column_xyz"


def test_broken_fk_is_critical_candidate_and_allow_critical_warns():
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "data"
        _generate_pack(out)

        materials_path = out / "materials.csv"
        with open(materials_path, "r", newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        rows[0]["supplier_id"] = "SUP-NOTFOUND"
        with open(materials_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

        rc, output = _run_semantic_ci(out)
        assert rc == 1, output
        report = _load_report(out)
        assert report["summary"]["gate_status"] == "FAIL"
        assert report["summary"]["critical_candidates"] > 0
        assert report["gates"]["governance_feedback"]["status"] == "FAIL"

        rc, output = _run_semantic_ci(out, ["--allow-critical", "--regenerate-mapping"])
        assert rc == 0, output
        report = _load_report(out)
        assert report["summary"]["gate_status"] == "WARN"
        assert report["summary"]["critical_candidates"] > 0
        assert report["gates"]["governance_feedback"]["status"] == "WARN"
