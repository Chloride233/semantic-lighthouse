#!/usr/bin/env python3
"""Record and summarize local Phase 4 pilot-task observations.

The tool deliberately separates simulated rehearsals from real-user sessions.
It performs no networking and does not write application or production data.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


SESSION_TYPES = ("simulated", "real_user")
OUTCOMES = ("completed", "incomplete", "abandoned")
DEFAULT_PROTOCOL_ID = "phase4-manufacturing-v1"
UNVERSIONED_PROTOCOL_ID = "unversioned"


def _parse_timestamp(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError("timestamps must use ISO 8601 format") from exc
    if parsed.tzinfo is None:
        raise ValueError("timestamps must include a UTC offset or Z")
    return parsed.astimezone(timezone.utc)


def _record(args: argparse.Namespace) -> int:
    started_at = _parse_timestamp(args.started_at)
    completed_at = _parse_timestamp(args.completed_at)
    if completed_at <= started_at:
        raise ValueError("completed-at must be later than started-at")
    if not args.protocol_id.strip():
        raise ValueError("protocol-id cannot be empty")

    record = {
        "schema_version": 1,
        "record_id": str(uuid4()),
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "protocol_id": args.protocol_id,
        "session_type": args.session_type,
        "participant_id": args.participant_id,
        "task_id": args.task_id,
        "outcome": args.outcome,
        "started_at": started_at.isoformat(),
        "completed_at": completed_at.isoformat(),
        "duration_seconds": int((completed_at - started_at).total_seconds()),
        "failure_points": args.failure_point,
        "manual_edit_count": args.manual_edit_count,
        "feedback": args.feedback,
    }
    args.record_file.parent.mkdir(parents=True, exist_ok=True)
    with args.record_file.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    print(json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _load_records(record_file: Path) -> list[dict[str, Any]]:
    if not record_file.is_file():
        raise ValueError(f"record file not found: {record_file}")

    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(record_file.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"record file line {line_number} is not valid JSON") from exc
        if not isinstance(record, dict):
            raise ValueError(f"record file line {line_number} is not an object")
        records.append(record)
    return records


def _metrics(records: list[dict[str, Any]]) -> dict[str, int | float | None]:
    completed = [record for record in records if record.get("outcome") == "completed"]
    durations = [record["duration_seconds"] for record in records if isinstance(record.get("duration_seconds"), int)]
    return {
        "session_count": len(records),
        "completed_count": len(completed),
        "completion_rate": round(len(completed) / len(records), 3) if records else None,
        "median_duration_seconds": statistics.median(durations) if durations else None,
        "failure_point_count": sum(len(record.get("failure_points", [])) for record in records),
        "manual_edit_count": sum(record.get("manual_edit_count", 0) for record in records),
        "feedback_count": sum(len(record.get("feedback", [])) for record in records),
    }


def _cohort_summary(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cohorts: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for record in records:
        key = (
            str(record.get("protocol_id") or UNVERSIONED_PROTOCOL_ID),
            str(record.get("task_id") or "unknown"),
        )
        cohorts.setdefault(key, []).append(record)

    return [
        {
            "protocol_id": protocol_id,
            "task_id": task_id,
            "all_sessions": _metrics(cohort_records),
            "real_user_sessions": _metrics(
                [r for r in cohort_records if r.get("session_type") == "real_user"]
            ),
            "simulated_sessions": _metrics(
                [r for r in cohort_records if r.get("session_type") == "simulated"]
            ),
        }
        for (protocol_id, task_id), cohort_records in sorted(cohorts.items())
    ]


def _summary(args: argparse.Namespace) -> int:
    records = _load_records(args.record_file)
    cohorts = _cohort_summary(records)
    summary = {
        "schema_version": 1,
        "record_file": str(args.record_file),
        "cohort_count": len(cohorts),
        "cohorts": cohorts,
        "note": (
            "Metrics are cohort-specific. Do not combine protocol_id/task_id "
            "cohorts; only real_user_sessions support GitHub Issue #3 evidence."
        ),
    }
    rendered = json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Record local Phase 4 pilot-task observations.")
    subcommands = parser.add_subparsers(dest="command", required=True)

    record = subcommands.add_parser("record", help="Append one completed task observation.")
    record.add_argument("--record-file", type=Path, required=True)
    record.add_argument("--protocol-id", default=DEFAULT_PROTOCOL_ID)
    record.add_argument("--session-type", choices=SESSION_TYPES, default="simulated")
    record.add_argument("--participant-id", required=True, help="Use a pseudonymous study identifier.")
    record.add_argument("--task-id", required=True)
    record.add_argument("--outcome", choices=OUTCOMES, required=True)
    record.add_argument("--started-at", required=True, help="ISO 8601 timestamp with timezone.")
    record.add_argument("--completed-at", required=True, help="ISO 8601 timestamp with timezone.")
    record.add_argument("--failure-point", action="append", default=[])
    record.add_argument("--manual-edit-count", type=int, default=0)
    record.add_argument("--feedback", action="append", default=[])
    record.set_defaults(handler=_record)

    summary = subcommands.add_parser("summary", help="Summarize recorded observations.")
    summary.add_argument("--record-file", type=Path, required=True)
    summary.add_argument("--output", type=Path)
    summary.set_defaults(handler=_summary)
    return parser


def main() -> int:
    args = _parser().parse_args()
    if getattr(args, "manual_edit_count", 0) < 0:
        raise ValueError("manual-edit-count cannot be negative")
    return args.handler(args)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(2)
