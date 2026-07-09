# AdventureWorks Semantic CI 审计报告

日期：2026-07-09

## 审计范围

本次审计覆盖 AdventureWorks raw export 经 `map_adventureworks_to_semantic_pack.py` 映射后的离线 Semantic CI 产物：

- `.tmp/adventureworks-semantic/manifest.json`
- `.tmp/adventureworks-semantic/mapping_contract.json`
- `.tmp/adventureworks-semantic/rule_validation_report.json`
- `.tmp/adventureworks-semantic/governance_feedback.json`
- `.tmp/adventureworks-semantic/semantic_ci_report.json`

对照基线为 `.tmp/smoke-fde-auto-pack` 合成制造业包重新跑出的 Semantic CI 报告。

本次审计不覆盖：

- 应用数据库写入
- API 行为
- UI 行为
- 真实 governance issue 创建
- Agent/MCP/runtime 行为

## 依据原则

本次审计使用以下知识库原则作为判断框架：

- 语义库不是文档仓库，而是本体、指标定义、事件、映射和治理闭环构成的可演进资产。
- 知识图谱/数据关系只有在有业务语义、规则和动作边界时，才从“可查询”走向“可驱动业务流程”。
- 强关系、弱关系必须分层：分类、约束、合规、互操作走强关系；相似、召回、模糊关联走弱关系。
- BOM/MRP 建模要把物料角色、BOMLine、替代料、虚拟件、多视图和规则声明显式化，而不是只停留在父子外键。
- 人在回路不是橡皮图章，需要证据、风险、影响范围、owner 和可追溯的复核责任。
- Agent/AI 产出的治理建议必须有事实交叉验证、边界声明和人工确认，避免把幻觉或弱推断合法化。

参考文章目录位于 `D:\Ontology article\数据思考`，本轮重点参考：

- `20260705_AI时代企业的核心资产不是企业知识库，而是企业语义库！`
- `20260705_一文讲清本体工程化实践中的强关系、弱关系，以及适用场景`
- `20260611_用本体与物料主数据构建下一代BOM的方法论与实践架构`
- `20260623_如何利用本体建模来自动跑MRP？`
- `20260603_许多企业以为LLM+RAG+知识库_知识图谱就可以解决AI落地问题了，其实真正的分水岭是本体+Harness`
- `20260601_都说数据治理Agent中需要“人在回路”，那么对这个人有哪些要求？你的企业有这样的人吗？`
- `20260528_数据治理人必看：一文讲清AI幻觉对数据治理的影响`

## 结论摘要

AdventureWorks benchmark 已经能作为离线 Semantic CI 输入跑通，但当前更适合做“结构契约验证 + 派生类治理候选”的数据样例，还不能代表一个真正可落地的制造业语义操作层 benchmark。

关键事实：

- AdventureWorks semantic pack：13 表，187,508 行。
- Semantic CI 总状态：`WARN`。
- Hard failures：0。
- Critical candidates：0。
- Governance candidates：48。
- Data pack contract：PASS。
- Mapping contract：PASS。
- Business rules：PASS。
- Governance feedback：WARN。

核心判断：

- 当前映射在结构层是可用的：PK/FK、row count、enum、numeric、date order 都通过。
- 当前映射在语义层仍偏薄：BOM、MRP、指标、事件、动作、owner、人审闭环都还没有进入 contract。
- 48 个候选不是数据质量问题，而是模型增厚机会，集中在 `high_value_material` 和 `at_risk_equipment`。
- 相比合成制造业包，AdventureWorks 映射质量更稳定，但业务状态分布更单一，不能充分测试 HITL、异常处理、运行时闭环。

## Semantic CI 结果审计

| 项目 | AdventureWorks semantic pack | 合成 smoke pack |
|---|---:|---:|
| 总行数 | 187,508 | 279 |
| Semantic CI 状态 | WARN | WARN |
| hard failures | 0 | 0 |
| warnings | 1 | 2 |
| governance candidates | 48 | 103 |
| critical candidates | 0 | 0 |
| data quality / mapping review 候选 | 0 | 99 |
| ontology modeling opportunity 候选 | 48 | 4 |

解释：

- AdventureWorks 的 WARN 来自派生类识别，不是数据质量失败。
- 合成 smoke pack 的 WARN 主要来自 99 个 date_order 高严重度候选，说明生成器当前仍会制造不合理日期顺序。它适合测试治理反馈，但不适合当“干净业务样例”。
- AdventureWorks 映射在日期顺序上更可信，适合成为下一阶段 benchmark 主样例。

## 48 个候选审计

候选分布：

| derived_class | table | count | severity |
|---|---|---:|---|
| `at_risk_equipment` | equipment | 7 | info |
| `high_value_material` | materials | 41 | info |

源数据分布：

- equipment.status：`degraded=7`，`operational=7`。
- materials.abc_class：`A=41`，`B=152`，`C=311`。
- work_orders.status：`completed=72,591`，其他状态为 0。
- quality_inspections.result：`passed=42,384`，`failed=241`。

审计判断：

1. `at_risk_equipment` 候选合理，但当前证据太薄。
   - 触发逻辑只来自 equipment.status。
   - 缺少维护历史趋势、停机时长、校准超期、工位影响、关联 work order 影响范围。
   - 建议保留为 info 级候选，不应自动升级为真实 governance issue。

2. `high_value_material` 候选合理，但当前分类过粗。
   - 触发逻辑只来自 ABC=A。
   - 缺少库存价值、供应商风险、在途量、替代料、BOM 关键性、消耗速度。
   - 按知识库原则，它应进入“物料角色 + 指标体系 + BOMLine 影响分析”，而不是只作为材料标签。

3. 当前候选未形成闭环。
   - 已有 `requires_human_review=true`，但没有 owner、review SLA、复核结论、修复动作、二次验证。
   - 这符合离线边界，但离可运营治理还有距离。

## 与知识库原则的差距

### 1. 语义库资产仍不完整

当前已有：

- object types
- field mapping
- relationship mapping
- rule validation
- governance feedback candidate

仍缺：

- 指标定义：库存周转、供应风险、设备风险、质量失败率、工单准时率。
- 指标到本体映射：指标分子/分母、维度、来源表、绑定对象。
- 事件模型：工单释放、完工、报废、质检失败、维护完成。
- owner 和版本：每个对象/指标/规则/映射缺 owner、状态、变更历史。
- 复核闭环：candidate -> review -> decision -> applied model change -> rerun evidence。

结论：目前是“语义 contract + 离线 gate”，还不是完整语义库。

### 2. BOM/MRP 语义还停留在外键层

当前 BOM 结构：

- `bills_of_materials.product_id -> products.product_id`
- `bills_of_materials.material_id -> materials.material_id`
- 有 sequence、quantity、scrap、critical。

仍缺：

- BOMLine 作为一等实体的语义角色：normal、phantom、alternate、optional。
- BOM view：EBOM、MBOM、SBOM、as-built 等。
- effectivity：生效日期、版本、配置条件。
- 替代料组和优先级。
- MRP 行为规则：提前期偏移、净需求、安全库存、批量、供应商优先级。

结论：当前能验证 BOM 外键和用量，但不能验证“下一代 BOM/MRP”知识库原则。

### 3. 强/弱关系分层已起步，但离 runtime 语义还有距离

当前项目已实现 relation governance layer，但 AdventureWorks Semantic CI artifacts 本身还没有把关系分层写入 mapping/report：

- FK-derived relationships 可视为强候选，但尚未显式标注为 `approved_hard`。
- derived_class 候选属于弱到中等强度的治理信号，不能直接当硬关系或硬类型使用。
- quality inspection、equipment risk、high value material 都需要人审后才能变成强语义。

结论：项目方向正确，但 Semantic CI report 需要把“关系承诺级别”纳入输出。

### 4. HITL 审计表面还没有覆盖离线治理候选

当前任务页已有 evidence packet，但 Semantic CI candidate 仍停留在 JSON artifact。

缺口：

- candidate 没有 detail page。
- 没有 candidate owner。
- 没有 approve/reject/defer 状态。
- 没有 rollback note。
- 没有把候选映射成 modeling draft 的安全流程。

结论：HITL Evidence Packet 已在任务域起步，下一步应扩展到 governance candidate review。

### 5. AdventureWorks benchmark 状态分布单一

AdventureWorks 映射后的 work_orders 全部是 completed：

- 不能充分测试 pending/released/in_progress/on_hold/rejected 状态机。
- 不能充分测试 HITL 的“正在发生的风险”。
- 不能充分测试 runtime traversal 的运营场景，如延期风险、在制品瓶颈、未完成质检。

结论：AdventureWorks 是真实结构 benchmark，但还需要一个 scenario overlay，补出当前态/风险态。

## 当前开发进度判断

阶段判断：

- 已完成：离线 semantic CI gate、AdventureWorks raw export、AdventureWorks -> Semantic CI mapping。
- 已具备：用真实-ish 外部数据库导出的 CSV 跑完整离线语义交付门。
- 未完成：DB-backed governance review、runtime benchmark query、指标到本体映射、BOM/MRP 规则原型。

有效运行定义：

如果“真正有效跑起来”指离线验证链路：已经跑起来。

如果指产品级闭环：

```text
真实数据 -> semantic CI -> 人审治理候选 -> accepted modeling draft
-> model package -> dataset binding -> runtime traversal/query
-> outcome artifact -> 反馈回语义库
```

则当前完成约 45%-55%。缺的是后半段闭环，不是前半段数据接入。

## 下一步迭代建议

### P0: AdventureWorks Governance Candidate Review v1

目标：把 48 个候选从 JSON artifact 推进到可审阅的治理队列。

范围：

- 仍可先做离线 markdown/JSON review，不急着写 DB。
- 为每个候选补充：
  - source row identity
  - business object id
  - why triggered
  - affected scope
  - recommended decision
  - required human role

验收：

- 能回答“这 48 个候选哪些值得建模，哪些只是标签”。

### P1: Metric-to-Ontology Mapping MVP

目标：补知识库中最关键的“指标体系挂到本体上”。

建议先做 3 个指标：

- equipment risk rate
- high value inventory exposure
- quality failure rate

每个指标必须有：

- metric id
- formula
- numerator / denominator
- source tables
- dimensions
- ontology object/property bindings
- owner/review status

验收：

- Semantic CI report 能输出 metric mappings artifact。

### P1: BOM/MRP Semantic Overlay v1

目标：让 AdventureWorks 不只验证 BOM 外键，而是验证 BOM/MRP 语义。

新增离线 artifact：

- `bom_semantic_overlay.json`

至少表达：

- BOMLine type：normal / phantom / alternate / optional。
- effectivity。
- substitute group。
- MRP behavior rule tags。

验收：

- rule validation 能检查至少 3 条 BOM/MRP 规则。

### P2: Scenario Overlay for AdventureWorks

目标：修复 work_orders 全部 completed 导致的运营场景单一问题。

做法：

- 不改 raw export。
- 在 semantic mapping 阶段加可选 `--scenario-overlay active_ops`。
- 生成少量 deterministic 当前态：
  - released
  - in_progress
  - on_hold
  - rejected
  - failed inspection
  - degraded/down equipment impact

验收：

- 能跑出延期风险、质检风险、设备风险三类业务问题。

### P2: Synthetic Generator Date Order Fix

目标：修复合成 smoke pack 中 99 个 date_order 高严重度候选。

理由：

- 合成数据应能选择“clean benchmark”和“dirty governance benchmark”两种模式。
- 现在默认 smoke pack 会产生大量日期倒挂，不适合作为干净样例。

验收：

- `generate_manufacturing_dataset.py --preset tiny` 默认 Semantic CI 为 PASS 或仅 derived_class WARN。
- 需要 dirty case 时显式开启 anomaly preset。

## 总体建议

下一轮不建议直接做 Agent action 或 MCP。当前更应该先把 AdventureWorks 的离线 benchmark 打磨成语义闭环：

1. Governance Candidate Review v1。
2. Metric-to-Ontology Mapping MVP。
3. BOM/MRP Semantic Overlay v1。
4. Scenario Overlay for active operations。

这样项目会从“能跑数据契约”推进到“能解释业务风险、能沉淀语义资产、能形成治理闭环”。
