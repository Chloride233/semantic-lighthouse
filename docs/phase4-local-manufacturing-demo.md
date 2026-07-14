# Phase 4 Local Manufacturing Demonstration

## Purpose and Boundary

This is a five-minute, reproducible local rehearsal for GitHub Issue #3. It
shows the manufacturing ontology delivery chain and records a simulated task
observation. It does not recruit, contact, or measure real users. A simulated
record is not user-validation evidence and must not be reported as such.

The rehearsal uses the existing FDE smoke chain: a temporary SQLite database,
fake providers, and the deterministic synthetic manufacturing data pack. It
does not call an ERP, MES, PLC, external knowledge base, LLM, or Agent.

## Run

From the repository root:

```bash
.venv/bin/python scripts/run_phase4_manufacturing_demo.py
```

Optional: use a previously generated data pack.

```bash
.venv/bin/python scripts/generate_manufacturing_dataset.py \
  --preset tiny --seed 42 --output-dir .tmp/phase4-manufacturing
.venv/bin/python scripts/run_phase4_manufacturing_demo.py \
  --data-pack .tmp/phase4-manufacturing
```

Success requires `FDE Demo Smoke: PASS`, `Steps: 11 Passed: 11 Failed: 0`,
and `Rehearsal result: PASS`.

## Five-Minute Presenter Script

| Time | Demonstrate | Say |
|---|---|---|
| 0:00–0:35 | State the scenario: Plant 3 equipment reliability. | "The goal is to make maintenance evidence, a governed model, runtime reads, and a delivery record inspectable as one business chain." |
| 0:35–1:10 | Start the local rehearsal. | "This uses temporary SQLite data and fake providers, so it is reproducible without credentials or a running server." |
| 1:10–2:00 | Point to group, project, and evidence steps. | "The project is group-scoped; evidence is attached to the pilot before it informs the model or outcome." |
| 2:00–2:50 | Point to package and runtime steps. | "The package is quality-gated and immutable. Runtime reads are audited; this rehearsal does not execute a maintenance action." |
| 2:50–3:40 | Point to the outcome and artifact gate. | "The outcome preserves bounded evidence and package references, while the artifact gate rejects raw content, secrets, and storage paths." |
| 3:40–4:25 | Review the 11-step PASS summary. | "The complete path is validated locally, including the synthetic manufacturing data-pack contract." |
| 4:25–5:00 | Record the rehearsal and state the next gate. | "This record is explicitly simulated. Phase 4 remains open until 3–5 real users complete the task and their feedback drives an iteration." |

## Record a Rehearsal

Use a pseudonymous participant identifier and keep records outside Git:

```bash
.venv/bin/python scripts/record_pilot_task.py record \
  --record-file .tmp/phase4-task-records.jsonl \
  --participant-id rehearsal-001 \
  --task-id manufacturing-demo-v1 \
  --outcome completed \
  --started-at 2026-07-14T10:00:00+08:00 \
  --completed-at 2026-07-14T10:05:00+08:00 \
  --manual-edit-count 0 \
  --feedback "Local rehearsal completed without presenter intervention"
```

Summarize the records:

```bash
.venv/bin/python scripts/record_pilot_task.py summary \
  --record-file .tmp/phase4-task-records.jsonl
```

The summary always reports `real_user_sessions` separately from
`simulated_sessions`. Only records intentionally written with
`--session-type real_user` can support future Issue #3 user-validation
evidence. Do not enter names, email addresses, credentials, raw documents, or
other sensitive content in participant identifiers or feedback.

The fixed future task prompt, completion rubric, and timing boundary are in
`docs/phase4-manufacturing-pilot-protocol.md`. This rehearsal does not satisfy
that future real-user task.

## Deferred Issue #3 Work

- Recruit and observe 3–5 real users.
- Record task completion, duration, failure points, manual edits, and feedback.
- Implement and verify at least one product iteration based on that feedback.
- Publish the pilot result, boundary, and next decision with only real-user
  metrics represented as real-user evidence.
