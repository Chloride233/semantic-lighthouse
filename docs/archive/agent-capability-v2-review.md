# Agent Capability v2 设计审查

**Date**: 2026-06-17
**Reviewer**: 总控 reviewer
**Reviewed**: `docs/agent-capability-v2-design.md`, `agent_orchestrator.py`, `agent.py`, `test_agent.py`, `agent-handoff.md`, `project-roadmap.md`
**Verdict**: 有条件通过 — 3 个 must-fix，其余可延后

## 审查结论

| 维度 | 判定 |
|------|------|
| 设计整体 | ✅ 通过 |
| 安全约束（group_id/role/risky/whitelist） | ⚠️ 3/4 通过，risky 重复防护有缺口 |
| 状态机正确性 | ⚠️ execute gate + respond 需代码改动 |
| 测试策略 | ✅ FakeLoopChatClient 充分 |
| LLM output contract | ✅ call_tool / finalize 双 action 清晰 |
| max_steps 安全阀 | ✅ 硬上限 5 |
| migration | ✅ 确实不需要 |
| Handoff 同步 | ❌ 严重滞后 |
| Roadmap 同步 | ✅ 已更新 |

## 1. Handoff 与 Roadmap 对齐

**问题**: `docs/agent-handoff.md` 行 15 写 "Phase 7 — 7.5 not started"。实际已 delivered（17 tests, commits `48cc089` + `bc097ef`）。基线数字也过时：166 pytest → 175+, alembic 0010 → 0011。

**修正**: 更新 handoff to Phase 7.5 delivered + 引用 eval report + 引用 V2 design doc。

## 2. LLM Tool Loop 安全约束检查

**通过**: group_id 隔离（每步 get_membership_or_404）、role 权限（_validate_role in execute_tool）、tool whitelist（_tool_by_name gate）。

**缺口 — risky 重复防护**: 设计 §8 `respond("no")` 后 LLM 可再次提议同一 risky tool。无机制阻止循环：`propose archive → reject → propose archive → reject → ...`。

**修正**: 被拒后 observation 改为 `"User REJECTED the request to use 'archive_document'. Do NOT propose this tool again in this run."`

## 3. stopped / failed / completed 状态同步

**Schema**: `AgentRunResponse.status` 无 pattern 约束 → `stopped` 可直接加。✅

**execute gate**: 当前 `run.status not in ("planning", "executing")` 拦截 `awaiting_confirmation` 后的 execute。需加 `"awaiting_confirmation"`。

**respond endpoint**: 需加 "stop" 分支 → `run.status = "stopped"`。

**测试**: V2.1 需 `test_max_steps_exceeded_returns_stopped` + `test_user_stop_returns_stopped`。

## 4. tool_arguments 校验：不需要新依赖

运行时校验已在 `execute_tool` 中完成（`query.strip()`, `title.strip()`）。JSON Schema 格式仅用于 LLM function-calling prompt。不需要 `jsonschema` 依赖。

## 5. FakeLoopChatClient 测试覆盖

设计已定义 5 个场景。建议加第 6 个验证 risky 重复防护：

| # | 场景 | 预期 |
|---|------|------|
| 1 | simple search → finalize | completed |
| 2 | search error → retry → finalize | completed |
| 3 | max_steps exceeded | stopped |
| 4 | risky confirm → execute → finalize | completed |
| 5 | two-step list + search → finalize | completed |
| 6 | reject risky → try alternative | completed |

## 6. DeepSeek Smoke 时序

设计放 V2.2。**正确**。V2.1 核心风险是 while 循环逻辑正确性，fake provider 足够。真实 LLM 引入 token 成本/网络/API key——验证算法时是噪音。

## 7. V2.1 vs 延后

**V2.1 must-do**: agent_loop() (~50 行), execute 改 call agent_loop, FakeLoopChatClient (~30), 6 parametrized tests (~80), respond 修正 (+stop, no-finalize), execute gate 修正 (+awaiting_confirmation), risky 重复防护, handoff 更新, 回归 17 tests。总约 200 行。

**延后 V2.2**: DeepSeek agent_decide, Settings.agent_max_steps, plan_json, raw_llm_response。

**延后 V2.3**: 5 真实 LLM 场景, 指标对比, eval report 更新。

## 8. 风险清单

| 风险 | 等级 | 处置 |
|------|------|------|
| LLM 幻觉 tool_name | 高 | whitelist-gate → Error |
| LLM 无限循环 | 高 | max_steps=5 → stopped |
| LLM 绕过 risky | 高 | is_risky 执行层检查 |
| LLM 被拒后重复提议 risky | 高 | observation 写 Do NOT propose again |
| Prompt 注入 | 中 | goal user role; system JSON constraint |
| DeepSeek 格式不一致 | 中 | V2.2 smoke; V2.1 fake only |

## 9. 实现前置条件

1. Handoff 更新到当前真实基线
2. 设计文档 §8 补 risky 重复防护
3. 确认 execute gate + respond 端点修改范围

## 10. 验收标准

| 阶段 | 标准 |
|------|------|
| 设计 | 本审查 done; handoff 更新; design doc §8 修正 |
| V2.1 | 6 fake PASS; max_steps gate; risky 强制; 拒绝不重复; error→重试; audit 完整; 17 tests 回归; ruff clean |
| V2.2 | DeepSeek agent_decide 合法 JSON; smoke run completed |
| V2.3 | completion_rate ≥ 80%; risky 100%; audit 100%; before/after report |
