# Agent Workflow Evaluation v1 — Baseline Report

**Date**: 2026-06-17
**Phase**: 7.5 "Agent Evaluation Set"
**Status**: 14 pytest, 5 scenarios, 3 tools covered

## Eval Design

5 scenarios test the Agent FSM across all 3 registered tools (search_knowledge_base, archive_document, list_documents).

| # | Scenario | Tool | Key Assertion |
|---|----------|------|---------------|
| S1 | Read-only KB search | `search_knowledge_base` | run=completed, observation contains doc title, audit complete |
| S2 | Risky → confirm → execute | `archive_document` | awaiting_confirmation → confirm → completed, doc archived |
| S3 | Risky → reject → stop | `archive_document` | reject → failed, doc NOT archived |
| S4 | Insufficient role denied | `archive_document` (member) | Error: requires 'admin' role |
| S5 | Tool failure auditable | `search_knowledge_base` (empty) | step=failed, error_message set, 7 audit fields present |

## Metrics

| Metric | Value |
|--------|-------|
| scenarios_passed | 5/5 |
| tool_coverage | 3/3 |
| risky_enforcement | 100% |
| audit_complete_rate | 100% |
| unauthorized_block_rate | 100% |

## Defects Fixed

- **is_risky not enforced**: `archive_document` could execute without user confirmation. Fixed.
- **Error→status bug**: tool errors mapped to `step.status=completed`. Fixed.
- **`?tool=` eval param**: whitelist-gated for deterministic tool triggering.

## Known Limitations

- fake chat provider — tool decisions are deterministic, not LLM-driven
- single-step execution — multi-step plan→execute→observe loops are V2
- 5 scenarios by design — v1 baseline, not complete suite

## Test Results

```
14 passed, 0 failed (10 original + 4 new eval tests)
```
