# Phase 4 Manufacturing Pilot Task Protocol

## Status and Scope

Protocol version: `phase4-manufacturing-v1`.

This document prepares a single, comparable usability task for GitHub Issue #3.
It is a local protocol only: it does not recruit participants, contain a
contact list, or report any user metrics. The current rehearsal record remains
`simulated` and is not evidence that a user completed the task.

## Task

**Task ID:** `manufacturing-demo-v1`

**Participant prompt:**

> You are reviewing the Plant 3 equipment-reliability pilot. Run the local
> manufacturing rehearsal and explain whether the delivery chain has a valid,
> bounded outcome artifact. Identify one scope boundary that keeps this result
> from being a production maintenance action.

The prompt is intentionally fixed. Do not explain the desired answer before a
future participant responds, except to clarify a technical failure that blocks
the environment from starting.

## Completion Rubric

Mark the task `completed` only when the participant can independently:

1. run `scripts/run_phase4_manufacturing_demo.py` to a `Rehearsal result: PASS`;
2. identify that the FDE smoke completed all 11 checks and the artifact gate
   passed; and
3. state one supported boundary: the rehearsal uses temporary SQLite, fake
   providers, and synthetic data, and does not execute ERP, MES, PLC, Agent,
   or maintenance actions.

Mark `incomplete` when the participant cannot complete the task in the session,
and `abandoned` when they choose to stop. A failed system command is a failure
point, not evidence of participant failure by itself.

## Session Setup

Before a future session, the facilitator runs the same command once locally:

```bash
.venv/bin/python scripts/run_phase4_manufacturing_demo.py
```

Proceed only after the expected 11/11 PASS summary appears. The test uses
temporary SQLite state, so no prior participant data should be visible. Do not
pre-answer the task or modify the output while the participant is working.

## Measurement

Use a pseudonymous identifier such as `pilot-001`; do not record names, email
addresses, credentials, raw documents, or sensitive business content.

Start timing when the fixed prompt is shown. Stop when the participant answers
or abandons the task. Record every observed command failure, each manual change
to a command or input, and unprompted feedback in the existing local recorder:

```bash
.venv/bin/python scripts/record_pilot_task.py record \
  --record-file .tmp/phase4-task-records.jsonl \
  --protocol-id phase4-manufacturing-v1 \
  --session-type real_user \
  --participant-id pilot-001 \
  --task-id manufacturing-demo-v1 \
  --outcome completed \
  --started-at 2026-07-14T10:00:00+08:00 \
  --completed-at 2026-07-14T10:04:30+08:00 \
  --manual-edit-count 1 \
  --failure-point "Initial command omitted virtual environment prefix" \
  --feedback "The PASS summary was easy to interpret"
```

Summaries distinguish `real_user_sessions` from `simulated_sessions`, and
group metrics by `protocol_id` and `task_id`. Do not combine cohorts or session
types when calculating Issue #3 completion rate or task duration.

## Local Dry-Run

For the current no-contact iteration, run the task yourself with
`--session-type simulated`. Confirm that the command passes, the completion
rubric can be evaluated from its output, and the summary keeps
`real_user_sessions.session_count` at zero. This dry-run validates the
protocol mechanics only; it does not validate comprehension, usability, or
task duration for real users.

## Exit Conditions for This Preparation Slice

- The fixed task, time boundary, outcomes, and completion rubric are explicit.
- The recorder captures duration, failure points, manual edits, and feedback.
- Simulated records remain excluded from future real-user metrics.
- No user invitation or contact occurs in this slice.

The next Issue #3 activity remains a separate, user-authorized decision: invite
3–5 real users, collect their records, and make one product iteration based on
the resulting evidence.
