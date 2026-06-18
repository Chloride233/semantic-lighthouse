# Interview Demo Questions

Use these questions to demonstrate Semantic Lighthouse as an ontology-oriented semantic operating layer workspace for enterprise AI transformation. The current Phase 8 loop is: RAG → user-confirmed task → Agent/HITL → audit trail. Phase 9 will begin the ontology governance and graph layer.

---

## 北极星开场 (North Star Opener)

> 语义灯塔不是一个通用聊天机器人，也不是一个普通的 RAG 原型。它的目标是帮助企业把碎片化知识、文档、系统和流程，逐步建成权限感知、可审计、可操作、可被 Agent 安全调用的 Ontology 语义操作层。当前 Phase 8 完成的是可信证据→用户确认任务→受控 Agent→审计的全链路演示闭环。

Engineering points to hit:

- Every feature is explainable in business terms, technical terms, risk terms, and interview terms.
- Agent is a controlled coordination layer, not a replacement for deterministic backend logic.
- The destination is Ontology, not more RAG.

---

## Phase 8 Demo Script — Full Loop

### 8.0 知识导入与权限隔离

Steps:
1. 登录，创建/选择工作区（group）。
2. 导入 knowledge-graph 下的 ontology 知识文档（Markdown with YAML frontmatter）。
3. 展示文档列表，点击展开 frontmatter metadata（entityType, source, status 标签）。
4. 说明：每个文档、chunk、搜索、RAG 调用都按 `group_id` 隔离；非本组成员无法检索或引用其他组的知识库。

Interview talking point:

> 权限边界不在 prompt 里，在数据库查询条件和 membership 检查里。Agent 不能绕过。

---

### 8.1 RAG 回答：Citation、Confidence、Knowledge Gap

Question:

```text
企业已经有数据中台，为什么还需要 Ontology？
```

What it demonstrates:
- 混合检索（keyword + semantic）
- 引用溯源（citation：文档标题、片段、相关度评分、检索方式）
- 置信度判断（high / medium / low / unknown）
- 知识缺口列表（knowledge_gaps）
- local-evidence-gate：无证据时返回低置信度，不编造答案

Expected answer shape:
- 数据中台管理原始表/资产；Ontology 添加业务对象、关系、权限和工作流上下文
- AI 检索需要业务语义，不只是表名
- 引用 Ontology 源文档的 chunk

---

### 8.2 证据不足：知道什么时候不该回答

Question:

```text
请基于当前知识库评估某个未录入供应商的实施成本。
```

Expected answer shape:
- 无引用时返回 `confidence: low`
- 列出缺失的知识
- 建议补充供应商资料、实施案例、成本假设

Engineering point:

> 有用的企业 RAG 系统必须知道什么时候不该回答。拒绝或延迟也是答案质量的一部分。

---

### 8.3 用户确认任务：从回答到可追踪工作项

Steps:
1. 在问答页面提问，fake chat 返回 answer + next_steps。
2. 点击 "✓ 确认任务"。
3. 打开 `/tasks` 页面，看到刚确认的任务。
4. 展示 task card：标题、状态（待处理）、来源类型（RAG问答）、来源追溯。
5. 点击 task card 展开来源 RAG run detail：原始提问、回答、检索元数据。
6. 演示状态流转：pending → in_progress → done / cancelled。

What it demonstrates:
- RAG 输出不直接变成自动操作
- 用户确认是工作项创建的必要步骤
- 每个任务可追溯到原始 RAG 运行记录
- source_type 支持 rag_run / conversation / agent_run / manual

Interview talking point:

> Model can suggest, but human must confirm. This is a design decision, not a missing feature.

---

### 8.4 多轮对话：Citation、Tool Call、Context

Steps:
1. 打开 "对话" 页面，创建新对话。
2. 发送一条需要搜索的问题（例如 "Ontology 和 Knowledge Graph 的区别"）。
3. 展示 assistant 消息：
   - 置信度 badge
   - 上下文栏：🔍 混合检索 · 📄 3 条引用 · 模型：fake
   - 展开引用来源：标题、snippet、相关度、检索方式
   - 知识缺口列表
4. 如果触发了 tool call，展示 tool 消息：工具名、参数、结果摘要（长文本截断可展开）。
5. 展示失败状态：发送中按钮禁用 ("发送中...")，失败后恢复 input 和按钮，显示中文错误。

What it demonstrates:
- 多轮对话保持上下文
- 每条 assistant 消息都可见证据来源
- tool 调用过程透明可审计
- 错误状态用户友好

---

### 8.5 Agent / HITL / Audit

Steps:
1. 打开 "Agent" 页面。
2. 选择一个示例目标，或输入自定义目标（"列出当前知识库文档"）。
3. 点击 "启动 Agent"，看到新 run 出现在列表中。
4. 点击 "查看" 进入 run detail。
5. 点击 "执行下一步" → Agent 执行 plan / tool call。
6. 步骤时间线展示每一步：step_index、phase、thought、action_type、action_detail（可折叠 JSON）、observation、status。
7. 选择高风险目标（"归档标题包含 test 的文档"）→ run.status 变为 awaiting_confirmation。
8. 高风险确认卡片出现：⚠ 警告 + "确认执行" / "拒绝" / "停止运行" 按钮。
9. 点击 "确认执行" → 新的用户确认 step 出现在时间线中（带 "用户确认 ✓" 标签）。
10. Agent 执行确认的工具 → 新的 tool_call step + observation。
11. run 完成 → 展示 final_answer。

What it demonstrates:
- Agent 只是受控协调层，不是自主决策体
- 每一步都记录在审计时间线中
- 高风险操作必须经过用户确认（HITL）
- 用户确认/拒绝本身也是审计事件（HITL audit persistence）
- Agent 不能绕过权限检查、group_id 隔离、或确定性后端逻辑

Interview talking point:

> Agent 能力不是越多越好。System boundary > Agent flexibility.

---

### 8.6 生产安全

Talking points (no live demo needed):
- `APP_ENV=production` 时强制校验 JWT secret ≥ 32 chars、cookie_secure=true、DATABASE_URL ≠ 默认值。
- 失败关闭（fail closed）：配置错误 → 启动失败，而不是静默运行不安全的默认值。
- 密钥永不打印在日志中。

---

## Phase 9 Teaser — Ontology Core v1

> Phase 9 将开始把已有的 ontology KB 种子语料转成受治理的 ontology 实体、关系、校验问题和图谱/详情视图。这是从可信 RAG 走向语义操作层的第一步。

Planned (not yet built):
- Schema/frontmatter 校验：检测缺失必填字段、无效 entityType、entity/document type 冲突
- 实体抽取：导入文档产生 group-scoped ontology entity 记录
- Wikilink 关系抽取：`[[Entity]]` 变成显式关系候选
- 断链检测：标记缺失实体、重复标题/别名
- Ontology 图谱和实体详情 UI

---

## Two-Minute Demo Script (Quick)

1. 登录 → 选择工作区。
2. 知识问答 → 提问 "企业为什么需要 Ontology" → 展示 answer + citations + confidence + next_steps。
3. 确认任务 → 跳转任务面板 → 展示 source traceability。
4. Agent 页面 → 创建 run + 执行下一步 + 步骤时间线。
5. 对话页面 → 展示多轮上下文 + citation + tool call。

Closing line:

> 这不是一个通用 RAG demo，也不是一个自主 Agent 平台。这是一个从可信证据到受控操作、最终通向企业 Ontology 语义操作层的工程工作台。Phase 8 闭环已可演示，Phase 9 从治理和可见性开始。
