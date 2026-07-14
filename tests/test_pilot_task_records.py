"""Focused coverage for the local Phase 4 task-recording utility."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RECORDER = REPO_ROOT / "scripts" / "record_pilot_task.py"
DEMO = REPO_ROOT / "scripts" / "run_phase4_manufacturing_demo.py"


def _run_recorder(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(RECORDER), *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_record_writes_derived_duration_and_observation_fields(tmp_path):
    record_file = tmp_path / "records.jsonl"

    result = _run_recorder(
        "record", "--record-file", str(record_file),
        "--participant-id", "rehearsal-001", "--task-id", "manufacturing-demo-v1",
        "--outcome", "completed", "--started-at", "2026-07-14T10:00:00Z",
        "--completed-at", "2026-07-14T10:05:00Z", "--manual-edit-count", "2",
        "--failure-point", "artifact terminology", "--feedback", "clear flow",
    )

    assert result.returncode == 0, result.stderr
    record = json.loads(record_file.read_text(encoding="utf-8"))
    assert record["session_type"] == "simulated"
    assert record["duration_seconds"] == 300
    assert record["manual_edit_count"] == 2
    assert record["failure_points"] == ["artifact terminology"]
    assert record["feedback"] == ["clear flow"]


def test_summary_keeps_simulated_and_real_user_metrics_separate(tmp_path):
    record_file = tmp_path / "records.jsonl"
    common = (
        "record", "--record-file", str(record_file), "--task-id", "manufacturing-demo-v1",
        "--outcome", "completed", "--started-at", "2026-07-14T10:00:00Z",
        "--completed-at", "2026-07-14T10:05:00Z",
    )
    simulated = _run_recorder(*common, "--participant-id", "rehearsal-001")
    real = _run_recorder(
        *common, "--participant-id", "pilot-001", "--session-type", "real_user",
    )
    assert simulated.returncode == real.returncode == 0

    result = _run_recorder("summary", "--record-file", str(record_file))

    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)
    assert summary["all_sessions"]["session_count"] == 2
    assert summary["simulated_sessions"]["session_count"] == 1
    assert summary["real_user_sessions"]["session_count"] == 1
    assert "Only real_user_sessions" in summary["note"]


def test_record_rejects_non_positive_duration_without_writing(tmp_path):
    record_file = tmp_path / "records.jsonl"

    result = _run_recorder(
        "record", "--record-file", str(record_file),
        "--participant-id", "rehearsal-001", "--task-id", "manufacturing-demo-v1",
        "--outcome", "completed", "--started-at", "2026-07-14T10:05:00Z",
        "--completed-at", "2026-07-14T10:00:00Z",
    )

    assert result.returncode == 2
    assert "completed-at must be later" in result.stderr
    assert not record_file.exists()


def test_phase4_entrypoint_runs_existing_smoke_chain():
    result = subprocess.run(
        [sys.executable, str(DEMO)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "FDE Demo Smoke: PASS" in result.stdout
    assert "Steps: 11  Passed: 11  Failed: 0" in result.stdout
    assert "Rehearsal result: PASS" in result.stdout
