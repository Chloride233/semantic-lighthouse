# Palantir Ontology 四条链项目差距判断

日期：2026-06-23

## 核心判断

这句话抓住了 Palantir Ontology 热度背后的关键：

> 别急着把结论写成图数据库赢麻了；更该看的，是对象链先统一、关系链能查询、动作链敢写回、权限链能兜住。哪家公司先把这四件事接成闭环，哪家公司才算真的吃到这波热度。

对 Semantic Lighthouse 来说，方向是对的，但还没有完全做到闭环。

项目已经不只是“图画得像”。它有可信 RAG、证据链、Ontology draft、Business Contract、Mapping Contract、规则校验、runtime query 和 audit 这些真实工程骨架。但它还不是 Palantir 式完整 Ontology 操作层，因为关系查询和动作写回还没有形成业务闭环。

## 四条链评估

| 链路 | 当前项目状态 | 判断 |
|---|---|---|
| 对象链先统一 | 已有 OntologyDraft、OntologyModelPackage、Business Contract、Mapping Contract，把 CSV、manifest、dataset profile 映射成业务对象和属性。 | 基本做到 |
| 关系链能查询 | 有 link_type、relationship mapping、FK 校验，但 runtime query 目前仍偏单对象、字段过滤，还没有真正的关系遍历查询。 | 部分做到 |
| 动作链敢写回 | 有 Action Contract、Agent HITL、runtime audit，但项目边界仍明确禁止 data writeback，也没有真实业务动作执行。 | 还没做到 |
| 权限链能兜住 | group_id、owner/admin/member、runtime audit、Agent 风险动作确认、项目级 scope 都比较清晰。 | 做得最好 |

## 不能误判成图数据库问题

这个判断最重要的地方是：Ontology 的关键不是先上 Neo4j 或图数据库。

图数据库只能帮助表达和查询关系，但不能自动解决这些问题：

- 对象定义是否统一。
- 关系是否有业务语义。
- 动作是否可控、可审计、可回滚。
- 权限是否能覆盖查询、写入、Agent 工具调用和证据来源。

所以 Semantic Lighthouse 现阶段继续选择 PostgreSQL、JSON contract、离线 artifact、runtime audit 是合理的。当前更需要补的是语义闭环，而不是基础设施堆料。

## 改进建议

### 1. 先把 relationship mapping 变成 runtime 能力

下一步不应急着引入图数据库，而应先支持有限的关系路径查询。

示例目标：

```text
equipment -> work_orders -> maintenance_events
```

工程边界建议：

- 只支持已审核 package 中声明过的 link_type。
- 只允许白名单字段返回。
- 查询仍走 group_id、project_id、package semantic_hash。
- provenance 记录本次查询使用了哪些 object_type、link_type、binding 和 package。

这样可以证明“关系链能查询”，而不是只在文档和 JSON 里存在关系。

### 2. 把 Action Contract 推进到受控执行

不要一开始做任意业务写回。先做一个很窄、低风险、可审计的动作。

优先候选：

```text
create_governance_issue
create_work_order_candidate
accept_governance_feedback
```

最低安全要求：

- role check。
- human-in-the-loop confirmation。
- dry-run 预览。
- immutable audit。
- action status：proposed、confirmed、executed、rejected、cancelled。
- 不允许 Agent 直接决定最终写入。

这样可以从“有 Action Contract”升级为“动作链敢写回”。

### 3. 把 governance_feedback.json 入库

Phase 19 的 governance_feedback 目前还是离线 JSON artifact。下一步可以把它变成项目内可审查对象。

建议新增的业务概念：

- GovernanceIssue：治理问题。
- GovernanceSuggestion：系统建议。
- GovernanceDecision：人工接受、拒绝、延后。
- EvidenceReference：问题来自哪个 rule、dataset、mapping、RAG run 或 document。

这会形成更完整的闭环：

```text
数据质量发现 -> 规则校验 -> 治理反馈 -> 人审 -> 本体调整 -> 新 package -> runtime 使用
```

### 4. 继续强化权限链，但不要让权限只停在 API 层

当前权限链是项目强项，但后续进入关系查询和动作写回后，权限要继续下沉。

需要特别守住：

- 每条 relation traversal 都必须继承 group_id 和 project scope。
- 每个 action 都必须有 required_role。
- Agent 只能调用 server-side tool，不能传入自称的 group_id。
- audit 不记录 raw data、storage_path、filter value、PII 或 secret。
- 失败动作也必须留下 audit。

## 求职项目表达

面试时不要只说：

> 我做了一个 RAG + Ontology 项目。

更好的表达是：

> 我把项目从可信 RAG 推到语义操作层：先统一业务对象，再用 Business Contract 和 Mapping Contract 固化语义边界，然后通过规则校验、runtime query 和 audit 让语义模型可以被应用安全消费。当前项目已经完成对象链和权限链，关系链还处于有限查询前夜，动作链还没有进入真实写回。我下一步会补 relationship traversal 和受控 action writeback，让它从“可解释语义层”推进到“可操作语义层”。

这比宣称“复刻 Palantir”更可信。它说明我知道 Palantir Ontology 的真实难点不是图数据库，而是对象、关系、动作、权限四条链能不能接成闭环。

## 阶段结论

Semantic Lighthouse 当前可以定位为：

```text
可信 RAG -> 证据治理 -> Ontology 建模 -> Mapping Contract -> 规则校验 -> 只读 runtime
```

下一阶段如果要真正贴近 Palantir Ontology，需要推进为：

```text
统一对象 -> 可查询关系 -> 受控动作 -> 权限审计 -> 人机协同治理闭环
```

因此，项目目前“有骨架、有方向、有工程判断”，但还没到完整 Ontology 操作系统。最值得补的不是图数据库，而是关系查询和受控写回。
