"""Tests for Phase 19.5 governance feedback generation.

Covers:
  - Feedback generated from rule report has correct schema
  - Boundaries are enforced (offline_only, no DB writes, no real issues)
  - Candidates grouped by type and severity
  - Missing/malformed report fails clearly
  - --fail-on-critical works when critical candidates exist
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
GOV_GEN = REPO_ROOT / "scripts" / "generate_governance_feedback.py"


# ── Helpers ──────────────────────────────────────────────────────────────────

def _run(script: Path, args: list[str], timeout: int = 30) -> tuple[int, str]:
    import subprocess
    import sys
    result = subprocess.run(
        [sys.executable, str(script)] + args,
        capture_output=True, text=True, timeout=timeout,
    )
    # Combine stdout + stderr so error messages are visible
    combined = result.stdout + result.stderr
    return result.returncode, combined


def setup_full_data_pack(tmp_dir: Path) -> Path:
    """Generate data pack + mapping_contract + rule report."""
    out = tmp_dir / "data"
    rc, _ = _run(GEN_SCRIPT, [
        "--preset", "tiny", "--seed", "42", "--output-dir", str(out),
    ])
    assert rc == 0
    rc, _ = _run(MAP_GEN, ["--data-pack", str(out)])
    assert rc == 0
    rc, _ = _run(RULE_VAL, ["--data-pack", str(out)])
    # Rule validator may exit 1 due to date_order findings — that's OK
    # as long as the report was generated
    assert (out / "rule_validation_report.json").is_file()
    return out


def run_gov_gen(data_dir: Path, extra_args: list[str] | None = None) -> tuple[int, str]:
    """Run governance feedback generator."""
    args = ["--data-pack", str(data_dir)]
    if extra_args:
        args.extend(extra_args)
    return _run(GOV_GEN, args, timeout=15)


def load_feedback(data_dir: Path) -> dict:
    """Load governance_feedback.json."""
    return json.loads(
        (data_dir / "governance_feedback.json").read_text(encoding="utf-8")
    )


# ── Tests ────────────────────────────────────────────────────────────────────


class TestGovernanceFeedback:
    """Verify governance feedback generation (Phase 19.5)."""

    def test_feedback_generates_with_correct_schema(self):
        """Governance feedback has all required top-level fields."""
        with tempfile.TemporaryDirectory() as tmp:
            out = setup_full_data_pack(Path(tmp))
            exit_code, output = run_gov_gen(out)
            # May exit 0 (WARN with no critical) on clean synthetic data
            fb = load_feedback(out)

            # Top-level schema
            assert fb["feedback_version"] == "1.0"
            assert "generated_at" in fb
            assert fb["source_report"] == "rule_validation_report.json"
            assert fb["data_pack"] == "manufacturing"

            # Summary
            s = fb["summary"]
            assert "total_findings_in_report" in s
            assert "total_candidates" in s
            assert "by_type" in s
            assert "by_severity" in s
            assert "by_table" in s
            assert "requires_human_review" in s
            assert isinstance(s["by_severity"], dict)
            for sev in ("critical", "high", "medium", "info"):
                assert sev in s["by_severity"], f"Missing severity: {sev}"

            # Boundaries
            b = fb["boundaries"]
            assert b["offline_only"] is True
            assert b["writes_to_database"] is False
            assert b["creates_real_governance_issues"] is False
            assert b["replaces_human_review"] is False
            assert "note" in b

            # Candidates have correct structure
            for c in fb["candidates"]:
                for key in ("candidate_id", "finding_ref", "candidate_types",
                            "severity", "suggested_action", "status",
                            "evidence"):
                    assert key in c, (
                        f"Candidate {c.get('candidate_id', '?')} "
                        f"missing '{key}'"
                    )
                assert c["status"] == "open"
                assert c["severity"] in ("critical", "high", "medium", "info")
                assert len(c["candidate_types"]) >= 1

    def test_candidates_grouped_by_type_and_severity(self):
        """Candidates are correctly classified by type and severity."""
        with tempfile.TemporaryDirectory() as tmp:
            out = setup_full_data_pack(Path(tmp))
            run_gov_gen(out)
            fb = load_feedback(out)

            s = fb["summary"]
            # All candidates should have a valid type
            type_total = sum(s["by_type"].values())
            assert type_total > 0 or s["total_candidates"] == 0
            if s["total_candidates"] > 0:
                assert type_total >= s["total_candidates"]

            # Severities sum should match
            sev_total = sum(s["by_severity"].values())
            assert sev_total == s["total_candidates"]

            # Derived class findings should be info severity
            for c in fb["candidates"]:
                if "ontology_modeling_opportunity" in c["candidate_types"]:
                    assert c["severity"] == "info", (
                        f"Derived class should be info, got {c['severity']}"
                    )

    def test_missing_report_fails_clearly(self):
        """Generator exits 1 when rule_validation_report.json is missing."""
        with tempfile.TemporaryDirectory() as tmp:
            out = setup_full_data_pack(Path(tmp))
            # Delete the report
            (out / "rule_validation_report.json").unlink()

            exit_code, output = run_gov_gen(out)
            assert exit_code == 1, (
                f"Should exit 1 for missing report, got {exit_code}\n{output}"
            )
            assert "not found" in output.lower()

    def test_boundaries_not_creating_real_issues(self):
        """Feedback boundaries confirm no DB writes or real issue creation."""
        with tempfile.TemporaryDirectory() as tmp:
            out = setup_full_data_pack(Path(tmp))
            run_gov_gen(out)
            fb = load_feedback(out)

            b = fb["boundaries"]
            assert b["offline_only"] is True
            assert b["writes_to_database"] is False
            assert b["creates_real_governance_issues"] is False
            assert "not been written to the database" in b["note"].lower()

    def test_fail_on_critical_works_with_fk_violation(self):
        """--fail-on-critical exits 1 when critical (fk integrity) candidates
        exist."""
        with tempfile.TemporaryDirectory() as tmp:
            out = setup_full_data_pack(Path(tmp))
            # Create a critical violation: break FK by truncating suppliers
            csv_path = out / "suppliers.csv"
            with open(csv_path, "r", newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            if len(rows) > 1:
                with open(csv_path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                    writer.writeheader()
                    writer.writerows(rows[-1:])  # keep only last

            # Re-run rule validation to capture the FK violation
            _run(RULE_VAL, ["--data-pack", str(out)], timeout=15)

            # Generate feedback with --fail-on-critical
            exit_code, output = run_gov_gen(out, ["--fail-on-critical"])
            assert exit_code == 1, (
                f"Should exit 1 with --fail-on-critical when FK broken, "
                f"got {exit_code}\n{output}"
            )
            # Verify critical candidates exist
            fb = load_feedback(out)
            assert fb["summary"]["by_severity"]["critical"] > 0, (
                "Expected critical candidates after FK break"
            )

    def test_clean_data_without_critical_does_not_fail(self):
        """Default mode does not exit 1 when only non-critical candidates
        exist."""
        with tempfile.TemporaryDirectory() as tmp:
            out = setup_full_data_pack(Path(tmp))
            exit_code, output = run_gov_gen(out)
            # With clean synthetic data there may be WARN-level findings
            # but default mode should not exit 1 (only --fail-on-critical does)
            fb = load_feedback(out)
            critical = fb["summary"]["by_severity"]["critical"]
            if critical == 0:
                assert exit_code == 0, (
                    f"No critical candidates, should exit 0, "
                    f"got {exit_code}\n{output}"
                )
            # If there ARE critical candidates without --fail-on-critical,
            # exit should still be 0 (WARN, not FAIL)
