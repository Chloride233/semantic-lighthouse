# ECC Stage Prompts

本文件保存语义灯塔后续大阶段的 `/ecc plan` 提示词。推进到哪个阶段，就复制对应阶段的提示词给 Claude Code / ECC。

使用原则：

- 大阶段启动、涉及数据库、安全、RAG、Agent、部署时，先用 `/ecc plan`。
- 小范围 bug fix、文档错别字、单个测试修复，不需要强制使用 `/ecc plan`。
- 每次只推进一个阶段，不要一次性让 Agent 做完整路线图。
- 确认计划后，再使用文末的执行提示词。

## 阶段 0：工程基线稳定化

```text
/ecc plan

你正在接管 F:\semantic-lighthouse 项目。本轮目标是推进【阶段 0：工程基线稳定化】。请先不要写代码。

请先阅读：
1. CLAUDE.md
2. README.md
3. docs/agent-handoff.md
4. docs/project-roadmap.md
5. docs/engineering-memory/session-log-2026-06-11.md
6. 当前 git status 和最近 git log

本阶段目标：
把当前项目从“功能已经很多”整理成“可信工程基线”。

请围绕以下方向做计划：
1. V3.4 ETL 收尾验证：ingestion job、retry、failed、ready retry、step_log 持久化。
2. PostgreSQL + pgvector 真实 smoke，不只依赖 SQLite。
3. pytest、ruff、Alembic 空库迁移、gitignore、敏感信息隔离。
4. 更新 docs/agent-handoff.md 和工程记忆。

请输出最小可交付计划，必须包含：
- 当前状态判断
- 本轮只做什么
- 不做什么
- 需要检查或修改的文件范围
- 测试命令
- 验收标准
- 最高风险点
- 回滚方式

要求：
- 不做新功能
- 不进入阶段 1
- 不提交密钥、数据库、上传文件、运行产物
- 先 review/test，再决定是否需要修复
```

## 阶段 1：检索质量工程化

```text
/ecc plan

你正在 F:\semantic-lighthouse 项目中工作。本轮目标是推进【阶段 1：检索质量工程化】。请先不要写代码。

请先阅读：
1. CLAUDE.md
2. docs/agent-handoff.md
3. docs/project-roadmap.md
4. 当前 documents、chunks、keyword search、semantic search、RAG 相关代码和测试

本阶段目标：
让检索从“能搜到”升级为“能评估、能解释、能优化”。

请围绕以下方向做计划：
1. 建立检索评测集：20 到 50 个代表性 query，每个 query 有期望命中文档或 chunk。
2. 增加检索指标：Recall@K、无结果率、误召回样例。
3. 设计 hybrid search：保留关键词检索，结合向量检索，先不引入 Elasticsearch。
4. 检索结果解释：返回 retrieval_method、score、source_path、chunk_id、document_id。

请输出最小可交付计划，必须包含：
- 当前检索实现现状
- 新增评测数据放在哪里
- 是否需要新增 API 或只做内部评测脚本
- hybrid search 的最小实现方案
- 对 RAG 的影响
- 测试计划
- 验收标准
- 不做什么

要求：
- 暂不引入 Elasticsearch
- 暂不引入 rerank
- 不破坏现有 keyword search 和 semantic search
- 所有检索必须继续带 group_id 权限隔离
```

## 阶段 2：知识治理与文档生命周期

```text
/ecc plan

你正在 F:\semantic-lighthouse 项目中工作。本轮目标是推进【阶段 2：知识治理与文档生命周期】。请先不要写代码。

请先阅读：
1. CLAUDE.md
2. docs/agent-handoff.md
3. docs/project-roadmap.md
4. documents、document_chunks、upload_sessions、ingestion_jobs 相关模型、migration、API 和测试

本阶段目标：
让知识库不只是能入库，而是能管理、能追溯、能控制质量。

请围绕以下方向做计划：
1. 文档状态管理：uploaded、processing、ready、failed、archived。
2. 文档版本与删除策略：软删除、版本追溯、同组同 hash 秒传兼容。
3. 来源可信度建模：利用 source、status、documentType、parser、frontmatter。
4. 检索和 RAG 默认排除 archived / failed 文档。

请输出最小可交付计划，必须包含：
- 当前文档生命周期现状
- 是否需要 migration
- API 变化
- 对 import-local、upload、chunked upload、ETL 的影响
- 对 keyword/vector/RAG 检索的影响
- 测试计划
- 验收标准
- 回滚方式

要求：
- 不做复杂 CMS
- 不做前端管理后台
- 不破坏已有文档入库链路
- group_id 必须继续贯穿 documents、chunks、jobs、search
```

## 阶段 3：RAG 回答质量强化

```text
/ecc plan

你正在 F:\semantic-lighthouse 项目中工作。本轮目标是推进【阶段 3：RAG 回答质量强化】。请先不要写代码。

请先阅读：
1. CLAUDE.md
2. docs/agent-handoff.md
3. docs/project-roadmap.md
4. RAG answer、retrieval、LLM provider、rag_runs、citation 相关代码和测试

本阶段目标：
让 RAG 不只是“调用大模型”，而是具备咨询式回答、引用、可信度和知识缺口。

请围绕以下方向做计划：
1. 稳定回答契约：answer、citations、confidence、knowledge_gaps、next_steps。
2. 引用校验：citation 必须来自本次检索结果，不能由模型编造。
3. 无证据处理：证据不足时明确说明不足，而不是强答。
4. RAG 评测集：10 到 20 个标准问答样例，检查引用正确率和拒答质量。

请输出最小可交付计划，必须包含：
- 当前 RAG 链路现状
- 回答结构是否需要 schema 强校验
- citation 校验方案
- 失败与降级策略
- rag_runs 审计需要记录哪些字段
- 测试计划
- 验收标准
- 不做什么

要求：
- 不做 Agent
- 不做复杂 prompt framework
- 不允许模型编造 citation
- 不把无依据回答包装成高可信答案
```

## 阶段 4：V4 Agent 多轮对话

```text
/ecc plan

你正在 F:\semantic-lighthouse 项目中工作。本轮目标是推进【阶段 4：V4 Agent 多轮对话】。请先不要写代码。

请先阅读：
1. CLAUDE.md
2. docs/agent-handoff.md
3. docs/project-roadmap.md
4. RAG answer、rag_runs、auth/group 权限、documents search 相关代码和测试

本阶段目标：
在 RAG 稳定后，引入受控 Agent 多轮咨询能力，而不是做不可控的炫技 Agent。

请围绕以下方向做计划：
1. 会话与短期记忆：conversation/session，保存用户问题、检索结果、回答摘要。
2. 权限隔离：所有 memory、conversation、agent run 必须绑定 user_id 和 group_id。
3. 受控工具：Agent 只能调用明确工具，例如检索、追问、总结、生成建议。
4. 审计链路：每一步工具调用和模型输出都能追溯。

请输出最小可交付计划，必须包含：
- 当前 RAG 到 Agent 的最小扩展路径
- 需要新增哪些数据表或字段
- 需要新增哪些 API
- Agent 能做什么、不能做什么
- 多轮记忆如何隔离
- 测试计划
- 验收标准
- 风险点

要求：
- 不做全自动开放式 Agent
- 不允许模型自由执行高风险动作
- 不做复杂工作流引擎
- 不引入 LangGraph / AutoGen，除非能解释清楚且确实必要
```

## 阶段 5：云端部署与运维能力

```text
/ecc plan

你正在 F:\semantic-lighthouse 项目中工作。本轮目标是推进【阶段 5：云端部署与运维能力】。请先不要写代码。

请先阅读：
1. CLAUDE.md
2. docs/agent-handoff.md
3. docs/project-roadmap.md
4. Dockerfile、docker-compose.yml、docker-compose.prod.yml、.env.example、.env.production.example、部署文档

本阶段目标：
让项目具备真实工程交付感，能部署、能恢复、能排查、能复现。

请围绕以下方向做计划：
1. Docker Compose 生产部署流程固化：构建、上传、启动、迁移、回滚。
2. 健康检查：API、数据库、pgvector、可选 provider smoke。
3. 日志与安全：不记录 token、cookie、API Key，关键链路有可排查日志。
4. 成本与稳定性：embedding 批量、LLM 调用超时、失败降级、云端资源限制。

请输出最小可交付计划，必须包含：
- 当前部署现状
- 需要补充的部署文档
- 需要补充的 smoke 脚本或命令
- 是否需要调整 compose
- 云端验证步骤
- 回滚方式
- 测试计划
- 验收标准

要求：
- 不引入 Kubernetes
- 不引入复杂 CI/CD
- 不提交 .env.production
- 不把服务器密码、API Key、token 写进文档
```

## 阶段 6：前端工程化展示台

```text
/ecc plan

你正在 F:\semantic-lighthouse 项目中工作。本轮目标是推进【阶段 6：前端工程化展示台】。请先不要写代码。

请先阅读：
1. CLAUDE.md
2. README.md
3. docs/agent-handoff.md
4. docs/project-roadmap.md
5. 当前 API 路由、认证 cookie/token 机制、文档入库、检索、RAG、ingestion jobs 相关代码

本阶段目标：
在后端权限、检索、RAG、审计链路稳定后，建设一个真实可维护的前端控制台，而不是临时 demo 页面。

请围绕以下方向做计划：
1. 信息架构：登录、群组、文档、上传进度、ETL job、检索评测、RAG run 审计。
2. 权限感知 UI：Owner/Admin/Member 看到不同操作入口。
3. 文档与入库管理：上传、进度、失败原因、retry、archive。
4. RAG 演示体验：问题、检索片段、引用、可信度、知识缺口、下一步建议。
5. 前端测试：关键链路用浏览器测试验证。

请输出最小可交付计划，必须包含：
- 当前前端现状
- 推荐技术栈和理由
- 页面与路由拆分
- API 对接方式
- 权限状态如何表达
- 错误状态和加载状态
- 测试计划
- 验收标准
- 不做什么

要求：
- 不做营销 landing page
- 不做复杂视觉炫技
- 不绕过现有认证和 group_id 权限
- 不把前端做成无法解释的“大而全后台”
- 优先保证演示链路清晰、工程结构可维护
```

## 阶段 7：高级 Agent 编排

```text
/ecc plan

你正在 F:\semantic-lighthouse 项目中工作。本轮目标是推进【阶段 7：高级 Agent 编排】。请先不要写代码。

请先阅读：
1. CLAUDE.md
2. docs/agent-handoff.md
3. docs/project-roadmap.md
4. V4 conversation/session、RAG answer、rag_runs、retrieval、auth/group 权限相关代码和测试

本阶段目标：
在 V4 受控多轮 Agent 跑通后，升级为更复杂但仍然可解释、可审计、可控的 Agent 工作流。

请围绕以下方向做计划：
1. Tool registry：每个工具有明确输入 schema、输出 schema、权限要求和失败语义。
2. Agent workflow state：计划、执行、观察、总结分步骤持久化。
3. 长期记忆治理：记忆作用域、保留策略、删除策略、引用规则。
4. Human-in-the-loop：高风险动作需要用户确认后执行。
5. Agent 评测：多步任务成功率、引用质量、越权防护、失败恢复。

请输出最小可交付计划，必须包含：
- 当前 V4 Agent 能力边界
- 为什么需要更复杂的 Agent 编排
- 是否需要引入 LangGraph / AutoGen / 自研轻量编排
- 数据表和 API 影响
- 工具权限模型
- 审计字段
- 测试计划
- 验收标准
- 不做什么

要求：
- 不做不可控的开放式 Agent
- 不允许模型绕过权限直接操作数据
- 不把复杂框架当作亮点，必须说明它解决什么问题
- 每个 Agent 决策都要能追溯、能解释、能失败恢复
```

## 计划确认后的执行提示词

确认某个阶段的 plan 之后，再给 Claude Code / ECC 这句执行提示：

```text
按刚才确认的 plan 执行。请先跑现有测试，再做最小改动，最后重新运行相关测试，并更新 docs/agent-handoff.md 和必要的 engineering-memory 文档。不要扩大范围。
```
