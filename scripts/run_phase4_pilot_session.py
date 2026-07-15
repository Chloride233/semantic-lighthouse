#!/usr/bin/env python3
"""Run one observed Phase 4 manufacturing pilot session on a local Mac."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.record_pilot_task import _load_records, _record  # noqa: E402


TASK_ID = "manufacturing-demo-v1"
ROUND1_PROTOCOL_ID = "phase4-manufacturing-v1"
ROUND1_LIMIT = 2
ROUND2_LIMIT = 3
DEFAULT_RECORD_FILE = REPO_ROOT / "pilot-records" / "phase4-task-records.jsonl"
DEFAULT_ITERATION_FILE = REPO_ROOT / "pilot-records" / "phase4-iteration.json"
DEFAULT_PYTHON = REPO_ROOT / ".venv" / "bin" / "python"
DEMO_SCRIPT = REPO_ROOT / "scripts" / "run_phase4_manufacturing_demo.py"


def _preflight(python_path: Path = DEFAULT_PYTHON, demo_path: Path = DEMO_SCRIPT) -> None:
    if not python_path.is_file():
        raise ValueError(f"local Python not found: {python_path}")
    if not demo_path.is_file():
        raise ValueError(f"manufacturing rehearsal not found: {demo_path}")


def _real_user_count(records: list[dict], protocol_id: str) -> int:
    return sum(
        record.get("session_type") == "real_user"
        and record.get("protocol_id") == protocol_id
        and record.get("task_id") == TASK_ID
        for record in records
    )


def _load_iteration(iteration_file: Path) -> dict | None:
    if not iteration_file.exists():
        return None
    try:
        marker = json.loads(iteration_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("iteration marker is not valid JSON") from exc
    if not isinstance(marker, dict) or not marker.get("protocol_id"):
        raise ValueError("iteration marker is missing protocol_id")
    return marker


def _next_round(record_file: Path, iteration_file: Path) -> tuple[str, str]:
    records = _load_records(record_file) if record_file.exists() else []
    round1_count = _real_user_count(records, ROUND1_PROTOCOL_ID)
    if round1_count < ROUND1_LIMIT:
        return "round1", ROUND1_PROTOCOL_ID

    iteration = _load_iteration(iteration_file)
    if iteration is None:
        raise ValueError(
            "Round 1 is complete. Record a product iteration before starting Round 2."
        )
    protocol_id = str(iteration["protocol_id"])
    if protocol_id == ROUND1_PROTOCOL_ID:
        raise ValueError("Round 2 requires a new protocol_id")
    if _real_user_count(records, protocol_id) >= ROUND2_LIMIT:
        raise ValueError("Round 2 is already full")
    return "round2", protocol_id


def record_iteration(iteration_file: Path, protocol_id: str, summary: str, record_file: Path) -> None:
    if not protocol_id.strip() or protocol_id == ROUND1_PROTOCOL_ID:
        raise ValueError("iteration requires a new non-empty protocol_id")
    if not summary.strip():
        raise ValueError("iteration summary cannot be empty")
    if iteration_file.exists():
        raise ValueError("iteration marker already exists and cannot be overwritten")

    records = _load_records(record_file) if record_file.exists() else []
    if _real_user_count(records, ROUND1_PROTOCOL_ID) < ROUND1_LIMIT:
        raise ValueError("two Round 1 real-user records are required before an iteration")

    iteration_file.parent.mkdir(parents=True, exist_ok=True)
    iteration_file.write_text(
        json.dumps(
            {
                "protocol_id": protocol_id,
                "summary": summary.strip(),
                "recorded_at": datetime.now(timezone.utc).isoformat(),
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ) + "\n",
        encoding="utf-8",
    )


def record_session(
    *,
    record_file: Path,
    iteration_file: Path,
    participant_id: str,
    outcome: str,
    manual_edit_count: int,
    failure_points: list[str],
    feedback: str,
    started_at: datetime,
    completed_at: datetime,
) -> None:
    if not participant_id.strip():
        raise ValueError("participant ID cannot be empty")
    if not feedback.strip():
        raise ValueError("feedback cannot be empty")
    if manual_edit_count < 0:
        raise ValueError("manual edit count cannot be negative")

    _round_name, protocol_id = _next_round(record_file, iteration_file)
    args = argparse.Namespace(
        record_file=record_file,
        protocol_id=protocol_id,
        session_type="real_user",
        participant_id=participant_id.strip(),
        task_id=TASK_ID,
        outcome=outcome,
        started_at=started_at.astimezone(timezone.utc).isoformat(),
        completed_at=completed_at.astimezone(timezone.utc).isoformat(),
        failure_point=[point for point in failure_points if point],
        manual_edit_count=manual_edit_count,
        feedback=[feedback.strip()],
    )
    _record(args)


def _ask(prompt: str) -> str:
    return input(prompt).strip()


def _ask_outcome(default: str) -> str:
    options = "completed, incomplete, abandoned, failed"
    value = _ask(f"Outcome [{default}] ({options}): ") or default
    if value not in {"completed", "incomplete", "abandoned", "failed"}:
        raise ValueError("outcome must be completed, incomplete, abandoned, or failed")
    return value


def _run_interactive_session(record_file: Path, iteration_file: Path) -> int:
    _preflight()
    round_name, protocol_id = _next_round(record_file, iteration_file)
    print(f"\nPhase 4 {round_name} session ({protocol_id})")
    participant_id = _ask("Pseudonymous participant ID: ")
    print(
        "\nParticipant task: Run the manufacturing rehearsal, confirm its 11/11 PASS "
        "and artifact gate, then name one boundary preventing a production action."
    )
    _ask("Press Enter when the participant is ready to begin: ")
    started_at = datetime.now(timezone.utc)
    result = subprocess.run([str(DEFAULT_PYTHON), str(DEMO_SCRIPT)], cwd=REPO_ROOT)
    completed_at = datetime.now(timezone.utc)
    default_outcome = "completed" if result.returncode == 0 else "failed"
    outcome = _ask_outcome(default_outcome)
    manual_edits = _ask("Manual edit count [0]: ") or "0"
    try:
        manual_edit_count = int(manual_edits)
    except ValueError as exc:
        raise ValueError("manual edit count must be an integer") from exc
    failures = _ask("Failure points, separated by semicolons (blank for none): ")
    feedback = _ask("Required short feedback: ")
    record_session(
        record_file=record_file,
        iteration_file=iteration_file,
        participant_id=participant_id,
        outcome=outcome,
        manual_edit_count=manual_edit_count,
        failure_points=[point.strip() for point in failures.split(";")],
        feedback=feedback,
        started_at=started_at,
        completed_at=completed_at,
    )
    print(f"\nSaved anonymous session to {record_file}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run or advance a Phase 4 pilot session.")
    parser.add_argument("--record-file", type=Path, default=DEFAULT_RECORD_FILE)
    parser.add_argument("--iteration-file", type=Path, default=DEFAULT_ITERATION_FILE)
    parser.add_argument("--record-iteration", action="store_true")
    parser.add_argument("--protocol-id")
    parser.add_argument("--iteration-summary")
    args = parser.parse_args()

    if args.record_iteration:
        if args.protocol_id is None or args.iteration_summary is None:
            raise ValueError("recording an iteration requires --protocol-id and --iteration-summary")
        record_iteration(args.iteration_file, args.protocol_id, args.iteration_summary, args.record_file)
        print(f"Recorded iteration marker at {args.iteration_file}")
        return 0
    return _run_interactive_session(args.record_file, args.iteration_file)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(2)
