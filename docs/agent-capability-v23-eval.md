# Agent Capability V2.3 — Real LLM Smoke & Evaluation

**Date**: 2026-06-18
**Status**: Delivered — 39 tests (34 existing + 5 eval), smoke script ready

## Smoke: `scripts/smoke_agent_deepseek.py`

3 short calls, low token cost. Validates DeepSeek returns legal AgentDecision.
SKIP (exit 0) without DEEPSEEK_API_KEY.

| S | Scope | Expected |
|----|-------|----------|
| S1 | LLM output | action=="finalize", final_answer non-empty |
| S2 | LLM output | tool_name non-empty, tool_arguments is dict |
| S3 | LLM output | ChatError raised |

Scope: LLM output validation only. ChatError → 502 audit verified by pytest.

## Eval: `tests/test_agent_eval.py`

5 fake-provider scenarios, CI-safe.

| ID | Scenario | Assertion |
|----|----------|-----------|
| E1 | Finalize with useful answer | completed, audit fields present |
| E2 | call_tool list_documents | multi-step, observation has ready docs |
| E3 | Archived doc excluded | observation excludes archived title |
| E4 | Risky → confirmation | requires_confirmation in action_detail |
| E5 | Invalid tool → error | failed step with error_message |

Metrics: tool_choice_correct, permission_respected, audit_complete, unsafe_action_blocked.

## Results

```
39 passed: 23 test_agent + 7 test_chat_client + 5 test_agent_eval
ruff clean
```

## Known Limitations

- Real LLM non-determinism not measured
- 5 eval scenarios cover core dimensions but not exhaustive
- Smoke validates LLM output shape, not Agent run lifecycle
