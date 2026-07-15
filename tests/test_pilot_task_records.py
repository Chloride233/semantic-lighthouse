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
    assert record["protocol_id"] == "phase4-manufacturing-v1"
    assert record["session_type"] == "simulated"
    assert record["duration_seconds"] == 300
    assert record["manual_edit_count"] == 2
    assert record["failure_points"] == ["artifact terminology"]
    assert record["feedback"] == ["clear flow"]


def test_summary_keeps_cohorts_and_session_types_separate(tmp_path):
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
    second_task = _run_recorder(
        "record", "--record-file", str(record_file), "--participant-id", "rehearsal-002",
        "--protocol-id", "phase4-manufacturing-v2", "--task-id", "manufacturing-demo-v2",
        "--outcome", "incomplete", "--started-at", "2026-07-14T10:00:00Z",
        "--completed-at", "2026-07-14T10:03:00Z",
    )
    assert simulated.returncode == real.returncode == second_task.returncode == 0

    result = _run_recorder("summary", "--record-file", str(record_file))

    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)
    assert summary["cohort_count"] == 2
    assert "all_sessions" not in summary
    cohorts = {(c["protocol_id"], c["task_id"]): c for c in summary["cohorts"]}
    first = cohorts[("phase4-manufacturing-v1", "manufacturing-demo-v1")]
    assert first["all_sessions"]["session_count"] == 2
    assert first["simulated_sessions"]["session_count"] == 1
    assert first["real_user_sessions"]["session_count"] == 1
    second = cohorts[("phase4-manufacturing-v2", "manufacturing-demo-v2")]
    assert second["all_sessions"]["completion_rate"] == 0.0
    assert "Do not combine" in summary["note"]


def test_summary_labels_legacy_records_as_unversioned(tmp_path):
    record_file = tmp_path / "records.jsonl"
    record_file.write_text(
        json.dumps({
            "task_id": "legacy-task", "session_type": "simulated",
            "outcome": "completed", "duration_seconds": 30,
            "failure_points": [], "manual_edit_count": 0, "feedback": [],
        }) + "\n",
        encoding="utf-8",
    )

    result = _run_recorder("summary", "--record-file", str(record_file))

    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)
    assert summary["cohorts"][0]["protocol_id"] == "unversioned"


def test_feedback_correction_is_append_only_and_not_counted_as_session(tmp_path):
    record_file = tmp_path / "records.jsonl"
    created = _run_recorder(
        "record", "--record-file", str(record_file),
        "--participant-id", "pilot-001", "--task-id", "manufacturing-demo-v1",
        "--outcome", "completed", "--started-at", "2026-07-15T10:00:00Z",
        "--completed-at", "2026-07-15T10:04:00Z", "--feedback", "clear",
    )
    assert created.returncode == 0, created.stderr
    record_id = json.loads(created.stdout)["record_id"]

    correction = _run_recorder(
        "correct-feedback", "--record-file", str(record_file), "--record-id", record_id,
        "--feedback", "Could not interpret the PASS output.",
        "--reason", "Facilitator corrected the entered feedback after the session.",
    )
    assert correction.returncode == 0, correction.stderr

    summary = _run_recorder("summary", "--record-file", str(record_file))
    assert summary.returncode == 0, summary.stderr
    payload = json.loads(summary.stdout)
    assert payload["feedback_correction_count"] == 1
    assert payload["cohorts"][0]["all_sessions"]["session_count"] == 1


def test_report_refuses_insufficient_real_user_evidence(tmp_path):
    record_file = tmp_path / "records.jsonl"
    for participant_id in ("pilot-001", "pilot-002"):
        result = _run_recorder(
            "record", "--record-file", str(record_file), "--session-type", "real_user",
            "--participant-id", participant_id, "--task-id", "manufacturing-demo-v1",
            "--outcome", "completed", "--started-at", "2026-07-14T10:00:00Z",
            "--completed-at", "2026-07-14T10:04:00Z", "--feedback", "clear",
        )
        assert result.returncode == 0, result.stderr

    output = tmp_path / "report.md"
    result = _run_recorder(
        "report", "--record-file", str(record_file),
        "--protocol-id", "phase4-manufacturing-v1", "--task-id", "manufacturing-demo-v1",
        "--output", str(output), "--iteration-summary", "Improved copy.",
        "--time-change-note", "No baseline.", "--boundary", "Local only.",
        "--decision", "Do not close the pilot.",
    )

    assert result.returncode == 2
    assert "requires at least 3 real_user records" in result.stderr
    assert not output.exists()


def test_report_uses_one_real_user_cohort_and_excludes_simulated_records(tmp_path):
    record_file = tmp_path / "records.jsonl"
    outcomes = ("completed", "completed", "incomplete")
    for index, outcome in enumerate(outcomes, 1):
        result = _run_recorder(
            "record", "--record-file", str(record_file), "--session-type", "real_user",
            "--participant-id", f"pilot-{index:03}", "--task-id", "manufacturing-demo-v1",
            "--outcome", outcome, "--started-at", "2026-07-14T10:00:00Z",
            "--completed-at", f"2026-07-14T10:0{index}:00Z",
            "--failure-point", "command typo" if index == 3 else "",
            "--feedback", f"feedback {index}",
        )
        assert result.returncode == 0, result.stderr
    simulated = _run_recorder(
        "record", "--record-file", str(record_file), "--participant-id", "rehearsal-001",
        "--task-id", "manufacturing-demo-v1", "--outcome", "completed",
        "--started-at", "2026-07-14T10:00:00Z", "--completed-at", "2026-07-14T10:05:00Z",
        "--feedback", "rehearsal",
    )
    assert simulated.returncode == 0, simulated.stderr

    output = tmp_path / "report.md"
    result = _run_recorder(
        "report", "--record-file", str(record_file),
        "--protocol-id", "phase4-manufacturing-v1", "--task-id", "manufacturing-demo-v1",
        "--output", str(output), "--iteration-summary", "Clarified the command hint.",
        "--time-change-note", "No pre-iteration baseline was collected.",
        "--boundary", "Synthetic data and fake providers only.",
        "--decision", "Collect a post-iteration cohort before closure.",
    )

    assert result.returncode == 0, result.stderr
    report = output.read_text(encoding="utf-8")
    assert "Real-user sessions: 3" in report
    assert "Simulated sessions excluded: 1" in report
    assert "Completion rate: 66.7%" in report
    assert "Clarified the command hint." in report


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
