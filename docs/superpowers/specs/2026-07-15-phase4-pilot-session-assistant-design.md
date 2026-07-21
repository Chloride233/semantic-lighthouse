# Phase 4 Pilot Session Assistant Design

Status: Approved for implementation planning
Date: 2026-07-15
Lane: Standard for implementation

## Goal

Make five observed pilot sessions easy to run on the project owner's Mac without
asking participants to install software or asking the facilitator to type long
recording commands.

The owner only needs to:

1. invite two participants to test the current version;
2. return with their recorded feedback for one product iteration; and
3. invite three participants to test the improved version.

## Participant Flow

Each participant uses the owner's Mac in person or through screen sharing.
The facilitator starts one double-clickable entry point and enters a pseudonymous
participant ID. The assistant then:

1. checks that the local environment and rehearsal command are available;
2. displays the fixed participant task;
3. starts timing and lets the participant run the existing rehearsal;
4. collects the outcome, manual edit count, failure points, and short feedback; and
5. appends one anonymous record to the existing JSONL ledger.

The participant does not install dependencies, configure credentials, or provide
a name, email address, handle, or other personal information.

## Two-Round Gate

- Round 1 contains exactly two real-user sessions on the current version.
- After two complete Round 1 records, the assistant stops and requests a product
  iteration based on observed feedback.
- Round 2 begins only after the iteration is recorded as a new protocol version.
- Round 2 contains three real-user sessions on the improved version.
- Simulated rehearsals never count toward either round.

## Components

- A small Python session assistant owns preflight, timing, prompts, validation, and
  calls into the existing record format.
- A macOS `.command` file provides the double-clickable entry point and delegates all
  behavior to the Python assistant.
- The existing manufacturing rehearsal remains the only demo implementation.
- The existing JSONL recorder remains the source of truth for session records and
  formal reports.

No web UI, installer, background service, external account, or model call is added.

## Validation And Failure Behavior

The assistant refuses to write a record when the participant ID is empty, the
environment preflight fails, required feedback is missing, or the selected round is
already full. An interrupted or failed session may be recorded honestly as incomplete,
abandoned, or failed; it is never converted into a completed session.

The assistant must not overwrite the ledger. It appends validated records and reports
the saved path after each session. Focused tests cover preflight failure, successful
recording, missing feedback, round limits, and separation of the two versions.

## Completion Bar

- The entry point can be launched by double-clicking on macOS.
- One command covers preflight, timing, rehearsal, feedback, and recording.
- Two Round 1 sessions trigger the iteration stop.
- Three Round 2 sessions satisfy the post-iteration session gate.
- Existing simulated records remain excluded.
- Existing Phase 4 recorder and report behavior remains compatible.
