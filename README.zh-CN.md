# Semantic Lighthouse / 语义灯塔

[English](README.md)

Semantic Lighthouse 是一个面向企业 AI 转型的**本体导向语义操作层工作台**。它关注的不是“再做一个 RAG 聊天机器人”，也不是“做一个自治 Agent 平台”，而是把碎片化文档、知识、数据集、流程、权限、证据和 Agent 接口收束成一个**可审计的业务语义层**。

这个项目想证明的核心判断更窄，但也更强：

> 企业 AI 落地需要被治理的业务语义，而不只是模型调用。

## 它证明了什么

Semantic Lighthouse 演示了一条端到端的 FDE 风格交付链：

```text
业务目标
-> 作用域内证据
-> 人工审阅的本体模型
-> 质量门控后的 package
-> 数据集绑定
-> 类型化 runtime 查询
-> outcome 记录
-> 有边界的 markdown 交付物
-> 本体治理反馈
```

当前最强演示链路是 Phase 19 的制造业本体操作化流程：

```text
CSV
-> manifest.json
-> mapping_contract.json
-> rule_validation_report.json
-> governance_feedback.json
-> FDE smoke demo
```

## 如何运行 Demo

先生成一个合成制造业数据包：

```powershell
.\.venv\Scripts\python scripts\generate_manufacturing_dataset.py `
    --preset tiny --output-dir .tmp\phase19-manufacturing
```

然后跑完整的 FDE smoke：

```powershell
.\.venv\Scripts\python scripts\smoke_fde_demo.py `
    --data-pack .tmp\phase19-manufacturing
```

期望结果：

```text
FDE Demo Smoke: PASS | 11/11
Artifact gate: PASS
```

这条 smoke 使用 fake embedding/chat provider、临时 SQLite，不需要真实 API key。

## Phase 19 本体操作化流水线

先跑完整的离线 Semantic CI gate：

```powershell
.\.venv\Scripts\python scripts\run_semantic_ci.py `
    --data-pack .tmp\phase19-manufacturing
```

它会生成 `semantic_ci_report.json`，记录 gate 状态、artifact hashes、治理候选数量和人工审阅边界。

生成面向 reviewer 的治理候选审阅包：

```powershell
.\.venv\Scripts\python scripts\build_governance_review_packet.py `
    --data-pack .tmp\phase19-manufacturing
```

如果要跑 AdventureWorks benchmark，先导出 focused raw pack，再映射成
manufacturing contract，最后跑 Semantic CI：

```powershell
.\.venv\Scripts\python scripts\export_adventureworks.py `
    --ssh-target ubuntu@<server-ip> `
    --output .tmp\adventureworks

.\.venv\Scripts\python scripts\map_adventureworks_to_semantic_pack.py `
    --input .tmp\adventureworks `
    --output .tmp\adventureworks-semantic

.\.venv\Scripts\python scripts\run_semantic_ci.py `
    --data-pack .tmp\adventureworks-semantic `
    --regenerate-mapping --allow-critical

.\.venv\Scripts\python scripts\build_governance_review_packet.py `
    --data-pack .tmp\adventureworks-semantic

.\.venv\Scripts\python scripts\build_adventureworks_ontology_seed.py `
    --data-pack .tmp\adventureworks-semantic

.\.venv\Scripts\python scripts\build_governance_review_workspace.py `
    --data-pack .tmp\adventureworks-semantic
```

Ontology seed 会生成 `adventureworks_ontology_seed.json` 和
`adventureworks_ontology_seed.md`。它只是离线审阅 artifact：对象类型、
FK 关系候选和派生类候选仍需人工审阅，不能直接当作已发布模型包或 runtime
硬推理来源。
Review workspace 会为治理候选生成待决策记录，但不会应用模型变更，也不会创建真实治理 issue。

如果需要拆开看每一步，你也可以按下面的顺序跑离线治理链：

```powershell
# 1. 生成制造业数据包
.\.venv\Scripts\python scripts\generate_manufacturing_dataset.py `
    --preset tiny --output-dir .tmp\phase19-manufacturing

# 2. 校验数据包契约
.\.venv\Scripts\python scripts\validate_manufacturing_data_pack.py `
    .tmp\phase19-manufacturing

# 3. 生成字段到业务属性的 mapping
.\.venv\Scripts\python scripts\generate_mapping_contract.py `
    --data-pack .tmp\phase19-manufacturing

# 4. 校验 mapping contract
.\.venv\Scripts\python scripts\validate_mapping_contract.py `
    --data-pack .tmp\phase19-manufacturing

# 5. 跑确定性业务规则校验
.\.venv\Scripts\python scripts\validate_business_rules.py `
    --data-pack .tmp\phase19-manufacturing

# 6. 生成人工可审阅的治理反馈
.\.venv\Scripts\python scripts\generate_governance_feedback.py `
    --data-pack .tmp\phase19-manufacturing
```

Phase 19 收口产物：

| 产物 | 作用 |
|------|------|
| `manifest.json` | 13 张表、PK/FK、行数、核心 pilot 子集、业务语义 |
| `mapping_contract.json` | 13 个对象类型、15 条关系、受控 value/role/null 词表 |
| `rule_validation_report.json` | 8 类规则、确定性检查、有限 findings |
| `governance_feedback.json` | 人工可审阅的治理候选，按类型和严重度分组 |
| FDE artifact markdown | 有质量门的业务交付物 |

## 架构主链路

```text
认证与 group 隔离
-> 文档摄取
-> 混合检索
-> citation-grounded RAG
-> 用户确认的任务/动作
-> 受控 Agent/HITL 工作流
-> 本体治理
-> 建模草案
-> 质量门 package
-> business contract
-> dataset binding
-> runtime query
-> relationship traversal（1-2 hop、双向、可排序）
-> outcome artifacts
-> governance feedback
```

项目实现有意偏向**可解释的后端边界**，而不是堆叠更重的框架。

## 核心能力

- JWT 认证、BCrypt 密码哈希、refresh token 轮换、group RBAC
- 在 documents、retrieval、RAG、tasks、Agent runs、ontology、projects、datasets、bindings、outcomes、evidence links 等全链路强制 `group_id` 隔离
- Markdown / TXT / PDF / DOCX 文档摄取
- 基于 PostgreSQL/pgvector 的 keyword + semantic retrieval
- 带 citation、confidence、knowledge gaps、next steps 和审计记录的 RAG
- 带 tool registry、HITL 确认和 audit trail 的受控 Agent orchestration
- 实体、关系、validation issues、curation、modeling drafts 等本体治理能力
- 质量门控、不可变的 ontology model packages
- `Goal -> Data -> Model -> Validate -> Pilot` 的业务 pilot 工作流
- dataset profiling、确定性 modeling draft 生成、显式 dataset bindings
- FDE outcome records、outcome summaries、有边界的 markdown artifacts
- relationship runtime traversal：1-2 hop hash join、任意 OT 过滤、正反向遍历、grouped/flat 输出、稳定排序、explain-only、fail-closed audit、FK indexing 优化
- Phase 19 离线数据治理链：data pack -> mapping -> rules -> governance feedback

## 有意保持的边界

这些是刻意的产品边界，不是“还没补完”的 checklist：

- **没有 MCP runtime**：MCP 仍然只是未来可能的 Agent-facing adapter
- **没有 Graph RAG**：当前是 hybrid retrieval，不是 graph retrieval
- **没有 R3E2 aggregation**：COUNT/SUM/AVG 被刻意 deferred，避免 traversal 长成 DSL
- **没有自治 Agent 写入**：高风险写操作必须经过后端权限和人工确认
- **没有私有企业数据**：制造业数据包是 realistic synthetic data
- **AdventureWorks 仍然是离线 benchmark 路径**：`scripts/export_adventureworks.py`
  可以导出 focused raw CSV + manifest；
  `scripts/map_adventureworks_to_semantic_pack.py` 可以把它映射进完整
  Semantic CI contract。它不写入应用数据库，也不改变 runtime 行为
- **还没有 DB-backed governance feedback**：Phase 19 当前只产出离线候选
- **核心 runtime 不依赖 Neo4j、OWL reasoner、LangGraph、OSDK、Kubernetes**

## 本地启动

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
pip install -e .
docker compose up -d postgres
alembic upgrade head
uvicorn semantic_lighthouse.main:app --reload
```

OpenAPI 文档：

```text
http://127.0.0.1:8000/docs
```

本地脚本和测试也支持 SQLite smoke 模式；大多数 demo 脚本会自动创建临时数据库。

## 验证方式

优先跑与当前能力相关的 targeted checks，而不是默认全量回归：

```powershell
# Phase 19 相关测试
.\.venv\Scripts\python -m pytest `
    tests\test_manufacturing_data_pack.py `
    tests\test_business_rule_validation.py `
    tests\test_governance_feedback.py `
    -p no:cacheprovider

# FDE smoke
.\.venv\Scripts\python scripts\smoke_fde_demo.py `
    --data-pack .tmp\phase19-manufacturing

# 文档对齐检查
.\.venv\Scripts\python scripts\check_doc_alignment.py
```

完整 backend regression 和 UI smoke 按 lane 选择，见 `docs/development-workflow.md`。

## 关键文档

| 文档 | 作用 |
|------|------|
| `PRODUCT.md` | 产品定位与边界 |
| `docs/project-status.toml` | 当前项目状态的唯一事实源 |
| `docs/project-roadmap.md` | 当前决策路线图 |
| `docs/deployment-v3-cloud.md` | 云部署说明 |
| `docs/CODEMAPS/` | 架构、后端、数据与前端结构快照 |

## Public Repository Boundary

这是一个个人项目展示仓库，请注意：

- **不包含真实生产配置**：`.env.production` 未提交，示例文件只保留占位值
- **不包含真实 API keys 或 secrets**：`.env.example` 中 key 字段为空，生产环境会在运行时强制非默认 secrets
- **不包含私有 knowledge base**：默认 `knowledge_base_path` 是 `./knowledge-graph`，需要你自行创建
- **部署文档是参考流程**，不是某台真实服务器的快照

## 当前状态

规范化项目状态见：`docs/project-status.toml`

### 已交付

| 线 | 范围 | 状态 |
|----|------|------|
| Phase 1-18 | auth、ingestion、retrieval、RAG、Agent、ontology governance、modeling、contracts、pilot workflow、outcomes、deployment smoke、frontend baseline | Complete |
| Phase 19 | 离线本体操作化（CSV -> manifest -> mapping -> rules -> governance feedback） | Complete |
| R2 | relationship runtime traversal 基础能力（1-2 hop、API、audit） | Complete |
| R3A-R3F | runtime 增强：grouped response、filter pushdown、bidirectional traversal、sorting、FK indexing | Complete |

### 已延期

| 项目 | 原因 |
|------|------|
| R3E2 aggregation (COUNT/SUM/AVG) | 会跨入 DSL 边界，需要真实需求再开 |
| MCP runtime | 未来候选，当前只有 design doc |
| Graph RAG | 等 entity/relation read model 更稳定后再看 |
| AdventureWorks benchmark | 已有 raw export adapter 和 Semantic CI mapping adapter |
| DB-backed governance feedback | Safety Lane 候选，当前只有离线候选 |

### 下一步候选

当前项目处于一个 decision gate，不自动扩 phase。候选方向需要显式选择：

1. **Semantic CI/CD 产品化**：把 mapping、规则、证据和治理反馈变成可重复的交付纪律
2. **HITL evidence packet**：在确认写入前展示证据、受影响对象、风险和 rollback notes
3. **强/弱关系治理**：区分契约型关系、推断关系和弱关系，避免图谱边语义混杂
4. **AdventureWorks benchmark**：对比真实 benchmark 和合成制造业数据包的治理发现
5. **指标到本体映射 MVP**：把 KPI 连接到对象、属性、证据和 lineage，同时避免扩成通用 analytics DSL
