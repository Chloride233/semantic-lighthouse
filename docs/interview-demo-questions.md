# Interview Demo Questions

Use these questions to demonstrate Semantic Lighthouse as an ontology-oriented semantic operating layer workspace for enterprise AI transformation. The primary demo flow is the Phase 14 Guided Pilot five-stage chain: 目标 → 数据 → 模型审核 → 质量验证 → 激活查询. Supporting paths (RAG, Agent, Ontology governance) remain accessible via "更多工具".

---

## 北极星开场 (North Star Opener)

> 语义灯塔不是一个通用聊天机器人，也不是一个普通的 RAG 原型。它的目标是帮助企业把碎片化知识、文档、系统和流程，逐步建成权限感知、可审计、可操作、可被 Agent 安全调用的 Ontology 语义操作层。当前主演示链路是 Phase 14 引导式 Pilot 五阶段：目标定义→数据上传→模型草案审核→质量验证→激活查询。

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

## Phase 9–13 Delivered — Ontology Governance → Model Contracts

Phase 9–13 are **delivered** (2026-06-18/19). The "Planned" section above is now production code:

- **Phase 9**: Schema/frontmatter validation, entity extraction, wikilink relation extraction, broken-link detection, ontology graph and entity detail UI. Real KB demo: 74 docs → 74 entities, 186 relations, 97 issues.
- **Phase 10**: Governance issue triage, real KB curation demo (97→39 backlog), graph UX polish, evidence-to-ontology bridge.
- **Phase 11–12**: Ontology Modeling Drafts v1 + Quality Gates + Immutable Model Packages. 76 drafts from real KB, 434 tests.
- **Phase 13**: Typed Business Ontology Contract & Manufacturing Pilot v1. 12/12 review gates PASS.

These phases are the bridge from "RAG with citations" to "governed, quality-gated, contract-snapshot-able Ontology."

---

## Phase 14–17 FDE Demo — The Full Delivery Chain

This is the primary **2027 internship/portfolio interview demo**. It shows the
complete chain from a business problem to an auditable FDE delivery artifact.

### What Semantic Lighthouse Is (and Isn't)

> 语义灯塔不是一个通用聊天机器人，不是一个 RAG 原型，也不是一个自主 Agent 平台。它是一个 **Ontology 语义操作层工作台**——帮助企业把碎片化知识、文档、数据集和流程，逐步建成权限感知、可审计、可操作的语义层。当前主线是 **FDE (Future Data Engineer) Pilot Delivery Record**：从业务问题 → 受控证据 → 模型包 → 运行时查询 → 审计交付物。

**不是**：
- 不是另一个 LangChain/LlamaIndex RAG demo。
- 不是让 Agent 自动建模的知识图谱工具。
- 不是一套做了很多 feature 但没有主链路的实验项目。

**是**：
- 一个可证明的、端到端的业务交付链路，每一步都有权限检查、审计记录、证据溯源、风险声明。
- 每条链路都可以在 ~1 秒内用 smoke script 验证 (`scripts/smoke_fde_demo.py`, 11/11 PASS)。
- 每个交付物（outcome record, outcome-summary JSON, markdown artifact）都可以交给 FDE 审阅者或面试官。

### FDE 用户的业务视角

一个 FDE 用户（或面试官）打开语义灯塔后，经历的主链路：

```text
1. 注册/登录 → 创建 Demo Group（制造行业）
2. 创建 Pilot Project：Equipment Reliability Pilot — Plant 3
3. 定义 Business Goal：减少非计划停机，提高故障码可追溯性
4. 上传 seed dataset（synthetic work order CSV，8 行 12 列）
5. 链接证据：2 个 KB 文档 + 1 个 RAG 问答保存为 project evidence
6. 生成建模草案 → 审核 → 构建模型包（quality PASS）
7. 生成 runtime binding → 查询 work order 数据
8. 创建 PilotOutcomeRecord（decision + risks + next_actions）
9. 查看 outcome-summary JSON（聚合统计）
10. 下载 outcome-artifact.md（FDE 交付物）
11. 运行 artifact quality gate → PASS（0 findings）
```

### 为什么 Demo Seed 选制造业设备维护

| 理由 | 说明 |
|------|------|
| **业务对象清晰** | Equipment, WorkOrder, Site, Team — 四个 Object Type 天然存在，不需要凭空设计 |
| **数据集结构好** | 12 列 CSV（equipment_id, work_order_id, asset_type, priority, status, downtime_hours, failure_code...）有自然 PK/FK 关系 |
| **业务价值可量化** | "减少非计划停机" 是制造业的真实 KPI，不是模糊的 AI 愿景 |
| **不绑定电商** | 电商 demo 过于常见；制造业设备维护在 2027 企业 AI 面试中更有区分度 |
| **全部 synthetic** | 所有数据都是合成数据，不含真实企业信息、PII、设备序列号 |

### 主链路架构

```text
BusinessProject (Phase 14)
  → DatasetAsset (CSV profiling, PK/FK suggestions)
  → ProjectEvidenceLink (document + rag_run, user-confirmed)
  → OntologyModelingDraft → OntologyModelPackage (quality-gated)
  → OntologyDatasetBinding → OntologyRuntimeAudit (typed query)
  → PilotOutcomeRecord (Phase 16.1 — immutable delivery snapshot)
  → GET /outcome-summary (Phase 16.2 — JSON aggregation)
  → GET /outcome-artifact.md (Phase 16.4 — bounded markdown)
  → artifact quality gate (Phase 17.3 — PASS/FAIL/WARN)
  → smoke_fde_demo.py (Phase 17.2 — 11/11 steps, ~0.8s)
```

### FDE 交付物

| 交付物 | 格式 | 受众 | 说明 |
|--------|------|------|------|
| **Outcome Record** | JSON (DB) | 系统/审计 | 不可变快照：business_goal_snapshot, evidence_refs, package_refs, decision_summary, risks, next_actions |
| **Outcome Summary** | JSON (API) | 前端/后端 | 聚合视图：project + latest_outcome + evidence/package/runtime 统计 |
| **Markdown Artifact** | text/markdown | 面试官/FDE 审阅者 | 人类可读的完整交付报告，含 Business Goal, Evidence Summary, Package Summary, Runtime Summary, Provenance |

### Smoke Script：可证明的链路

```bash
.\.venv\Scripts\python scripts\smoke_fde_demo.py
```

运行结果（2026-06-21）：

```
=== FDE Demo Smoke (Phase 17.2) ===
  [PASS] register (0.20s)
  [PASS] login (0.21s)
  [PASS] create_group (0.21s)
  [PASS] create_project (0.23s)
  [PASS] seed_evidence (0.23s) — 2 docs + 1 rag_run + 3 evidence links
  [PASS] seed_package (0.23s) — 1 package v1 PASS (4 drafts)
  [PASS] seed_runtime (0.23s) — 2 audit records (bindings + query, 8 rows)
  [PASS] create_outcome (0.24s) — Plant 3 Equipment Reliability v1
  [PASS] outcome_summary (0.25s) — evidence=3 pkg=1 runtime=2 outcome=yes
  [PASS] outcome_artifact (0.26s) — size=1911B text/markdown
  [PASS] artifact_quality_gate (0.26s) — PASS (0 findings)
FDE Demo Smoke: PASS | 11/11 | ~0.8s
```

**关键工程属性**：
- 零外部依赖：fake embedding + fake chat provider，不需要 API key
- 临时 SQLite 数据库：启动前删除旧 DB，运行在 `.tmp/smoke-fde-demo.db`
- 不需要 uvicorn：FastAPI TestClient 在进程内直接调用
- 按步计时：每步显示耗时，便于识别瓶颈
- exit code 语义：0 = PASS, 非零 = FAIL

### 风险边界（必须讲清楚）

| 边界 | 说明 |
|------|------|
| **不自动写 Ontology** | 所有 draft/package/outcome 都是 human-reviewed 或 explicitly created；Agent 不能自动建模 |
| **不泄露 raw data** | outcome-summary 和 artifact 永不含 raw_answer, raw_prompt, source_path, storage_path, secret, token, password, stack_trace |
| **不做 Graph RAG** | Ontology 治理图谱存在（Phase 9），但检索仍用 hybrid search；Graph RAG 待 entity/relation 数据成熟 |
| **不做 MCP runtime** | MCP 是 future adapter candidate，设计文档存在（`mcp-agent-boundary-design.md`），但零实现 |
| **前端策略** | F2 已完成，前端不再冻结。未来 UI 工作使用 `ui-ux-pro-max-skill` Minimalism & Swiss Style，避免无控制的大改 |
| **不做真实企业数据** | seed dataset 全部 synthetic，不接入外部 KB、不自动抓取、不部署到云 |

### 工程价值（面试核心论点）

| 价值点 | 具体体现 |
|--------|---------|
| **Group isolation** | 每个 group 的 document/chunk/RAG/evidence/package/runtime 全部 `WHERE group_id = :gid`；不是在 prompt 里做隔离 |
| **Auditable evidence** | 每条 project evidence link 有 provenance（来源类型、状态、时间戳），不暴露 raw content/path |
| **Bounded artifact** | markdown artifact 经过 7-section/11-forbidden-term/5-boundedness-rule 质量门校验 |
| **Deterministic backend** | 权限检查、状态过滤器、hash 校验、CRUD 全部走确定性后端逻辑；Agent 只能调用，不能代替 |
| **HITL boundary** | 所有 Agent write 操作需要 `require_group_role` + `group_id` 隔离 + user confirmation；拒绝自动执行 |
| **Immutable outcome** | PilotOutcomeRecord 创建后不可修改/删除（v1），保留完整审计链 |

---

## Five-Minute Demo Script (Interview / FDE Review)

### 0:00–0:30 — 北极星定位

> "语义灯塔是我为 2027 企业 AI 实习/面试构建的 Ontology 语义操作层工作台。它不只是一个 RAG 应用——它从业务问题出发，经过受控证据、质量门模型包、运行时查询，最终产出一个可审计的 FDE 交付物。我会在 5 分钟内展示完整链路。"

### 0:30–1:30 — 业务 Pilot 解释

> "我选择制造业设备维护作为 demo 场景——有 Equipment、WorkOrder、Site、Team 四个业务对象，数据集 8 行合成数据，12 列。不是电商 demo，因为设备故障码可追溯性和非计划停机是真实的企业 AI 问题。"

打开 Phase 17 planning doc (`docs/phase17-planning.md` §17.1) 展示 seed contract。

### 1:30–2:30 — 后端链路 + Smoke

运行 smoke script：

```bash
.\.venv\Scripts\python scripts\smoke_fde_demo.py
```

逐行解释：
- "register → login → create_group → create_project：标准的多租户入口"
- "seed_evidence：2 个文档 + 1 个 RAG 问答保存为 project evidence"
- "seed_package：1 个质量门通过的 ontology model package"
- "seed_runtime：2 条 runtime audit 记录（bindings + query）"
- "create_outcome：通过 API 创建不可变的 PilotOutcomeRecord"
- "outcome_summary + outcome_artifact：聚合 JSON 和 markdown 交付物"
- "artifact_quality_gate：7 个必选章节 + 11 个禁用词 + 5 个边界规则 → PASS"

重点强调：**11/11 steps, fake providers, temp SQLite, ~0.8s**。

### 2:30–3:30 — Outcome Artifact 的价值

打开 smoke 生成的 markdown artifact（或展示 API response 的 markdown 内容）：

> "这是 FDE 交付物——一份结构化的、人类可读的、经过质量门校验的 markdown 报告。它包含 Business Goal、Evidence Summary（3 条证据，按 type/role 分类）、Ontology Package Summary（1 个 PASS 包，4 个草案）、Runtime Summary（2 次操作）、Decision/Risks/Next Actions。底部有 Provenance 声明——这份报告不含 raw prompts、answers、paths、secrets。"

### 3:30–4:00 — 边界和下一步

> "我刻意不做的事情和做了的事情一样重要。没有 Graph RAG——因为 entity/relation 模型需要生产数据才能可信。没有 MCP runtime——设计文档存在但零实现。没有 Agent 自动建模——所有写入都经过 human review。前端 F2 完成但不做大重构。"

> "下一步：扩展 seed dataset 到真实 CMMS 数据规模，或做 cloud deployment smoke。"

---

## 常见追问回答 (FAQ)

### Q: 和普通 RAG 有什么区别？

> 普通 RAG 是 "question → retrieve → answer"。语义灯塔的 RAG 只是整个链路里的一环。RAG 答案可以保存为 project evidence，evidence 可以生成 modeling draft，draft 经过 quality gate 变成 immutable package，package 绑定 dataset 产生 typed runtime query，query 结果 + evidence + decision 组成 outcome record，最终产生 auditable markdown artifact。每一步都有权限检查、group 隔离、审计追踪。这不是 "更好的 RAG"——这是 "从 RAG 到 Ontology 语义操作层的工程链路"。

### Q: 和知识图谱 demo 有什么区别？

> 知识图谱 demo 通常展示 "实体-关系-属性" 的图可视化。语义灯塔有 ontology graph（Phase 9），但这不是终点。终点是：governed entity → modeling draft → quality-gated package → business contract → dataset binding → typed query → outcome delivery。图谱是中间的可见性工具，不是交付物。

### Q: 为什么不是让 Agent 自动建模？

> Agent 自动建模（"根据数据自动生成 Ontology"）有三个问题：第一，Agent 可能把 noise 当 signal（把临时列当业务属性）；第二，Agent 没有业务 domain expert 的判断力（什么 failure_code 应该保留，什么是误输入）；第三，Agent 输出不可审计——如果模型出错了，你不知道是 prompt 问题、上下文问题、还是模型本身的问题。当前设计：Agent 可以建议，人类才能确认。Human-in-the-loop 是 feature，不是缺口。

### Q: 为什么先做 read-only runtime/smoke？

> Runtime 是 Ontology 的 "存在证明"——它证明你定义的 business object type 真的能 query 到数据。但 production write（修改真实数据集、执行 Action）需要生产环境的安全基础设施、回滚机制、变更审批——这些在单机 demo 里不成立。Read-only runtime + smoke 证明了 "chain works"，write readiness 是下一个工程台阶。

### Q: 如何扩展到真实企业数据？

> 真实数据接入需要三步：第一，把 synthetic CSV 替换为真实 CMMS/ERP 数据（保持列映射不变）；第二，用真实 embedding provider（替换 fake）做 semantic search；第三，部署到 PostgreSQL + pgvector（替换 SQLite）。当前代码已经支持 PostgreSQL——有 Alembic migration、有 pgvector HNSW 索引、有 docker-compose.prod.yml。扩展是 config change，不是 rewrite。

---

## Deprecated Sections

The Phase 8 and Phase 9 sections above are retained for historical reference. The
current primary demo is the **Phase 14–17 FDE Delivery Chain** documented in
this section. The old "Two-Minute Demo Script" is replaced by the
"Five-Minute Demo Script" above.
