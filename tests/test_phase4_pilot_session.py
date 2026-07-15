"""Focused tests for the local Phase 4 observed-session assistant."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts import run_phase4_pilot_session as session  # noqa: E402
from scripts.record_pilot_task import _load_records  # noqa: E402


START = datetime(2026, 7, 15, 10, 0, tzinfo=timezone.utc)


def _record(record_file: Path, iteration_file: Path, participant_id: str, outcome: str = "completed"):
    session.record_session(
        record_file=record_file,
        iteration_file=iteration_file,
        participant_id=participant_id,
        outcome=outcome,
        manual_edit_count=0,
        failure_points=[],
        feedback="clear enough",
        started_at=START,
        completed_at=START + timedelta(minutes=4),
    )


def test_preflight_rejects_missing_local_environment(tmp_path):
    with pytest.raises(ValueError, match="local Python not found"):
        session._preflight(tmp_path / "missing-python", tmp_path / "missing-demo")


def test_session_records_anonymous_real_user_observation(tmp_path):
    record_file = tmp_path / "records.jsonl"
    iteration_file = tmp_path / "iteration.json"

    _record(record_file, iteration_file, "pilot-001")

    record = _load_records(record_file)[0]
    assert record["session_type"] == "real_user"
    assert record["protocol_id"] == "phase4-manufacturing-v1"
    assert record["participant_id"] == "pilot-001"
    assert record["feedback"] == ["clear enough"]


def test_session_refuses_missing_feedback_without_writing(tmp_path):
    record_file = tmp_path / "records.jsonl"
    with pytest.raises(ValueError, match="feedback cannot be empty"):
        session.record_session(
            record_file=record_file,
            iteration_file=tmp_path / "iteration.json",
            participant_id="pilot-001",
            outcome="completed",
            manual_edit_count=0,
            failure_points=[],
            feedback="",
            started_at=START,
            completed_at=START + timedelta(minutes=4),
        )
    assert not record_file.exists()


def test_round_limits_require_iteration_then_separate_new_protocol(tmp_path):
    record_file = tmp_path / "records.jsonl"
    iteration_file = tmp_path / "iteration.json"
    _record(record_file, iteration_file, "pilot-001")
    _record(record_file, iteration_file, "pilot-002")

    with pytest.raises(ValueError, match="Record a product iteration"):
        _record(record_file, iteration_file, "pilot-003")

    session.record_iteration(
        iteration_file,
        "phase4-manufacturing-v2",
        "Clarified the task wording after Round 1 feedback.",
        record_file,
    )
    for participant_id in ("pilot-003", "pilot-004", "pilot-005"):
        _record(record_file, iteration_file, participant_id)

    with pytest.raises(ValueError, match="Round 2 is already full"):
        _record(record_file, iteration_file, "pilot-006")

    records = _load_records(record_file)
    assert session._real_user_count(records, "phase4-manufacturing-v1") == 2
    assert session._real_user_count(records, "phase4-manufacturing-v2") == 3


def test_command_launcher_is_executable_and_uses_local_venv():
    launcher = REPO_ROOT / "scripts" / "run_phase4_pilot_session.command"
    content = launcher.read_text(encoding="utf-8")
    assert os.access(launcher, os.X_OK)
    assert ".venv/bin/python" in content
    assert "run_phase4_pilot_session.py" in content
