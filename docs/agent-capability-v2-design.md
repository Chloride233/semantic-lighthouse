# Agent Capability v2 — 受控 LLM Tool Loop 设计

**Date**: 2026-06-18
**Phase**: Agent Capability v2（V2.1 delivered, V2.2 pending）
**Status**: V2.1 implemented — fake loop, 23 agent tests. V2.2 DeepSeek smoke deferred.
**Depends on**: Agent Workflow Evaluation v1 (delivered, 17 tests)

## 1. 当前 deterministic FSM 如何工作

**状态机**: `planning → executing → (risky?) awaiting_confirmation → completed/failed`

**工具选择**: `POST /runs/{id}/execute?tool=X`。调用方（pytest/前端）决定用哪个工具，Agent 不做自主决策。默认 `search_knowledge_base`。`?tool=` 由 `AGENT_TOOLS` registry whitelist-gate。

**单步执行**: 一次调用一个工具，执行后立即 `finalize_run()`。没有观察→重规划循环。

**已验证约束**（17 tests）：group_id 隔离、role 权限、risky enforcement、error→status 映射、audit 7 字段、cross-group 隔离、unregistered tool 拒绝。

## 2. 为什么需要 LLM tool loop

当前 deterministic FSM 可以受控执行任意工具，但不能自主决策。具体缺口：

| 场景 | 当前 | 需要 |
|------|------|------|
| "帮我搜一下 Ontology" | 用户选 ?tool=search | LLM 分析 goal → 选 tool |
| "查一下 AI 转型相关文档，过时的归档掉" | ❌ 不可达 | LLM 先 search 再决定是否 archive |
| "我的知识库制造业案例够不够" | ❌ | LLM 先 list 再 search 再综合 |
| 搜索无结果 → 换关键词重试 | ❌ | LLM 观察结果 → replan → 重新 search |

核心价值不是换一种调用方式，而是让 Agent 观察结果后调整下一步。

## 3. 哪些场景真的需要 LLM 自主选工具

**Phase 1 支持**（3 个）：单步检索、检索+综合、检索+失败重试。
**Phase 2 支持**（2 个）：条件归档、多工具探索。
**不支持**：多 Agent、外部写操作、Agent 自动 commit/部署、跨 workspace。

## 4. 工具 schema 设计

从 `AGENT_TOOLS` 自动生成 LLM function-calling 格式。每个 `ToolDef` 新增 `parameters: dict`（JSON Schema fragment）。不新增 tool。

```python
TOOL_SCHEMAS_FOR_LLM = [
    {"type": "function", "function": {
        "name": "search_knowledge_base",
        "description": "Search the group knowledge base with a keyword query.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "Search query"}},
            "required": ["query"]}}}, ...
]
```

## 5. LLM 输出契约

```json
{"thought": "...", "action": "call_tool", "tool_name": "...", "tool_arguments": {...}}
```
或
```json
{"thought": "...", "action": "finalize", "final_answer": "..."}
```

约束：`tool_name` 必须 in AGENT_TOOLS；`tool_arguments` 必须满足 tool JSON Schema；解析失败 → `step.error_message`，不进 retry。

## 6. 状态机变化

**V2**: `planning → executing → (risky) awaiting_confirmation → executing → ... → completed/failed/stopped`

新增 `stopped` 状态（max_steps 触发）。`awaiting_confirmation` 后 respond 回到 `executing`，不 finalize。

## 7. max_steps 和停止条件

| 条件 | 结果 |
|------|------|
| step_count >= max_steps (default 5) | stopped |
| LLM action=finalize | completed |
| 连续 2 次 tool Error | failed |
| 连续 3 次 parse 失败 | failed |
| 用户 respond "stop" | stopped |

`max_steps` 通过 `Settings.agent_max_steps` 配置，API 硬上限 ≤10。

## 8. risky tool confirmation 中断和恢复

```
execute → LLM decides archive_document → is_risky → awaiting_confirmation
  → respond("yes") → execute_tool → observation 写回 → run=executing → 下一次 execute
  → respond("no") → observation="User REJECTED the request to use 'archive_document'. Do NOT propose this tool again in this run." → run=executing → 下一次 execute
```

确认/拒绝后不 finalize。Risky step 的 action_detail 保留 needs_confirmation 标记。

**拒绝后防重复规则**：用户拒绝 risky tool 后，step.observation 必须明确告知 LLM 不要在同一 run 中再次提议同一 tool。这不是 LLM 的"建议"，而是 observation 中的硬约束——LLM 解读 observation 后应选择 alternative tool 或 finalize。若 LLM 仍然再次提议被拒 tool，每轮 max_steps 消耗一步，最终由 max_steps 或连续 parse 失败触发终止。FakeLoopChatClient 场景 6 验证此行为。

## 9. tool error 反馈

Tool 返回字符串直接作为 observation 传给 LLM 下一轮 prompt。LLM 根据 error 内容决定 retry（换参数）或 finalize（诚实报告）。

## 10. audit trail

- 已有 7 字段保持不变（thought/action_type/action_detail/observation/error_message/started_at/finished_at）
- `thought` 从硬编码变为 LLM 产出
- `action_detail.raw_llm_response` 存前 500 chars
- `plan_json` 每步追加 LLM decision 摘要
- 不存完整 prompt（token 炸弹）

## 11. fake provider 测试

`FakeLoopChatClient`: 接受预定义 decision sequence，按 cursor 顺序返回。5 个 parametrized 场景：
- simple search → finalize
- search error → retry → finalize
- max_steps exceeded → stopped
- risky with confirm → execute → finalize
- two-step list + search → finalize

## 12. 真实 provider smoke

本地：`chat.py` 新增 `agent_decide()` 方法 + 手动 Python 脚本验证 JSON 回包。
云端：curl 执行 Agent run + curl execute × N 步直到 completed/stopped。
不做 CI 集成、不做性能基准。

## 13. 不做什么

LangGraph/AutoGen、多 Agent、Agent 自动创建任务、Agent 自动 commit、新工具类型、Web Search、自动重试策略、并行工具调用、Agent memory 影响决策、对话上下文 eval、迁移/新表、前端控制台。

## 14. Deep Agents / LangGraph 参考计划

LangChain Deep Agents / LangGraph 对本项目有参考价值，但当前只作为设计 pattern 来源，不作为运行时依赖引入。

**可吸收的 pattern**：
- todo/planning：把 Agent 中间计划显式化，类似 `write_todos`，但落到现有 `plan_json` / `agent_steps`。
- context offloading：长对话或长任务时保留可审计摘要，避免把完整上下文塞进 prompt。
- subagent isolation：未来如果需要专题分析，可借鉴“隔离上下文”的思想；当前不做多 Agent 调度。
- HITL：继续坚持 risky tool 必须用户确认，确认/拒绝都写入 audit。
- event flow：学习 observe → act → observe 的可回放结构，但仍用现有 FSM 和数据库表表达。

**不引入的部分**：
- 不引入 LangGraph / Deep Agents runtime。
- 不引入虚拟文件系统、代码执行沙箱、自动 commit/deploy。
- 不让 Agent 绕过 `group_id`、角色权限、文档状态过滤、任务确认等确定性后端规则。

**重新评估条件**：只有当轻量 `agent_loop()` 在真实多步骤场景中出现可测瓶颈（例如上下文恢复困难、图状态比 FSM 更清晰、HITL 恢复复杂度过高）时，才重新评估 LangGraph/Deep Agents runtime。

## 15. 分阶段实现

- **V2.0**（当前）：本设计文档
- **V2.1**：`agent_loop()` while 循环 + LLM decide + FakeLoopChatClient + 5 parametrized tests
- **V2.2**：真实 DeepSeek smoke + max_steps gate + stopped 状态 + 连续 error 检测
- **V2.3**：5 个真实 LLM 场景 + 指标对比 + eval report 更新

## 16. 是否需要 migration

**不需要。** 现有 `agent_runs.status` (String 20) 够存 `stopped`。`agent_steps` 7 字段足够。`plan_json` 已有。无新表、新列、新索引。

## 17. 风险清单

| 风险 | 缓解 |
|------|------|
| LLM 幻觉 tool_name | whitelist-gate in execute_tool |
| LLM 无限循环 | max_steps=5 硬上限 |
| LLM 绕过 risky | is_risky 在执行层强制检查，不依赖 LLM 判断 |
| LLM 被拒后重复提议同一 risky tool | observation 明确写 "Do NOT propose this tool again"；max_steps 兜底 |
| LLM tool_arguments 非法 | JSON Schema validate，失败→step error |
| Prompt 注入 | system prompt 以 JSON Schema 结束；goal 用 user role 传 |
| DeepSeek 格式不一致 | chat.py normalize 层 |

## 18. 验收标准

**设计阶段**: 本文档完整（18 节）+ handoff + roadmap 更新。
**实现阶段**: 5 fake 参数化 pass + max_steps gate + risky 不绕过 + error 反馈 + audit 完整 + DeepSeek smoke + 回归不退化。
**评测阶段**: completion_rate ≥ 80% + risky 100% + audit 100% + before/after 报告。
