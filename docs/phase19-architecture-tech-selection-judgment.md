# Semantic Lighthouse 架构与技术选型判断

日期：2026-06-22
性质：研究判断 / Phase 19 方向参考

## 总体判断

当前技术选型总体正确，不建议为了“Ontology 感”而过早引入重型框架。

Semantic Lighthouse 当前的优势不是技术栈复杂，而是边界清楚：FastAPI、SQLAlchemy、Alembic、PostgreSQL/pgvector、Pydantic、原生前端和受控 Agent registry 组成了一条可解释、可测试、可审计的企业 AI 工程链路。

下一步改进重点不应是换技术栈，而应是把 Ontology Runtime、数据映射、规则验证和治理反馈的架构边界进一步收紧。

## 应继续保留的技术选择

- FastAPI / SQLAlchemy / Alembic / Pydantic
- PostgreSQL + pgvector
- fake provider + smoke test 的验证策略
- 当前受控 Agent registry，而不是引入通用 Agent framework
- `draft -> human review -> package -> business contract -> runtime -> audit` 的主链路
- Phase 19.1/19.2 manufacturing data pack contract (realistic synthetic data, not real enterprise data)

这些选择符合项目定位：一个可演示、可解释、权限感知、审计友好的 Ontology semantic operating layer workspace。

## 暂缓引入的技术

以下技术有参考价值，但现在不应进入核心 runtime：

- Neo4j / 图数据库：当前实体关系复杂度还没有高到需要独立图存储。
- rdflib / OWL / HermiT：适合作为研究、导出或验证实验，不适合作为 Phase 19 核心依赖。
- LangGraph：当前 Agent FSM 尚未证明不够用。
- MCP runtime：继续保持未来 adapter 定位，不应提前实现。
- OSDK / SDK codegen：当前 business contract 还应先稳定。
- 自动 Action execution / writeback：这会进入高风险 Safety Lane，短期收益不如规则验证高。

## 架构改进重点

### 1. 拆清 Ontology Runtime 边界

当前 runtime 已承担 package lookup、binding、query、type conversion、dataset read、audit 等职责。Phase 19 如果继续加入 realistic business data pack（当前为 synthetic）、规则验证和异常反馈，应拆成更清晰的子层：

- contract context / semantic manifest
- dataset binding / mapping
- query execution
- rule validation
- audit / provenance

目标不是重构炫技，而是防止 runtime 继续膨胀成难以解释的“大服务”。

### 2. 把 Mapping Contract 升级为核心语义资产

当前 `OntologyDatasetBinding` 已经证明业务对象可以绑定到数据集。但下一步应让“字段如何变成业务属性”成为一等对象。

Mapping contract 应表达：

- 源字段
- 目标业务属性
- value type
- NULL 策略
- 枚举语义
- 证据来源
- 人工确认人
- 版本 hash / semantic hash

这比直接引入 OWL 更实际，也更符合项目当前链路。

### 3. 增加轻量规则验证层

Protégé / OWL 文章里的推理能力值得借鉴，但当前项目应先实现 deterministic business rule validation：

- 必填字段
- 唯一性
- 枚举范围
- 类型范围
- 互斥分类
- 派生类规则，例如 `HighValueOrder`
- 类型转换失败
- 未知枚举值
- 规则验证失败进入 governance issue 或 evidence-backed draft

这样可以证明 Ontology 不只是“能查数据”，而是能解释、验证和治理业务数据。

## 推荐 Phase 19 方向

Phase 19 建议定位为：

**Realistic Business Data Semantic Mapping + Rule Validation Loop**

一句话目标：

> 让 Semantic Lighthouse 证明 Ontology 不只是查询数据，而是能解释字段含义、验证业务规则、发现异常，并把异常反馈回人审建模流程。

推荐主链路：

```text
业务目标
-> 上传 real-or-simulated business data（当前为 realistic synthetic manufacturing data pack）
-> 生成或确认 mapping contract
-> 构建 package / business contract
-> 运行 typed query
-> 执行业务规则验证
-> 记录 runtime audit
-> 发现异常 / unknown / inconsistency
-> 生成 governance issue 或 evidence-backed modeling draft
-> 人审后进入下一版 package
```

## 方法论判断

两篇 Ontology 文章带来的共同启示是：

- Ontology 的价值不是“图谱可视化”，而是业务语义、规则、动作和治理边界的显式化。
- “动态 Ontology”不是系统自主进化，而是在人类预设框架内的可控适配。
- LLM 适合生成重复结构和辅助脚本，不适合替代建模决策。
- 未知对象、异常枚举、新概念和高风险动作必须进入人审流程。

这与 Semantic Lighthouse 当前方向一致。项目不应漂移成通用 RAG、通用 Agent 或通用图数据库 demo，而应继续强化：

```text
trusted evidence
-> reviewed ontology model
-> typed business contract
-> controlled runtime
-> audit and governance feedback
```

## 最终建议

短期不要换栈，不要追求 OWL/Graph/MCP/Agent framework 的“完整感”。

最值得做的是把现有架构推进到真实数据语义运营闭环：

1. mapping contract 一等化
2. runtime 服务拆边界
3. 规则验证轻量化
4. 异常反馈治理化
5. Phase 19 demo 围绕真实业务数据闭环展开
