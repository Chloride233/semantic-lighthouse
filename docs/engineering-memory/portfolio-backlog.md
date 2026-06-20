# Portfolio Backlog

本文件记录暂时不进入主路线图的求职展示与项目叙事材料。它不是当前阶段任务。

启动条件：

- 后端权限、文档入库、检索、RAG、Agent、前端控制台都达到你自己满意的完成度。
- 关键链路已经通过本地测试和云端 smoke。
- 项目能力可以被真实演示，而不是只停留在计划或未验证代码里。
- 你能讲清楚每个核心设计的业务意义、工程风险、验证方式和取舍原因。

## Future Phase: Job-Hunting Demo & Project Narrative

**Goal**: The project is presentable in interviews and portfolio reviews.

| Task | Acceptance |
|------|------------|
| Demo script with 5 scenarios | Register → upload → search → RAG → audit: 5-minute walkthrough |
| Architecture decision records (ADRs) | 5–8 ADRs covering key tradeoffs |
| One-page project overview (English) | Non-technical summary: what, why, how, key numbers |
| Interview Q&A preparation | 20 common questions with engineering answers |
| Public GitHub ready | README, license, contributing guide, clean commit history |

**Acceptance**: A stranger can clone, follow README, run demo, understand architecture from ADRs.

---

## Evidence-grounded Ontology Compiler — Main Portfolio Narrative (Phase 14.5+)

**Positioning**: Semantic Lighthouse is an **Evidence-grounded Ontology Compiler** — it compiles enterprise documents and data into an evidence-backed, human-reviewable, permission-isolated, queryable semantic runtime that Agents can safely use.

**Full chain** (all delivered as of Phase 14.5):

```text
Documents/Data → Dataset Profiling → Modeling Drafts → Human Review (accept/reject)
→ Quality-Gated Package (content hash, versioned) → Business Contract (semantic_hash)
→ DatasetBinding (explicit property→column mapping) → Unified Query Runtime
→ (future) Agent/MCP Adapter (reuses query service, no direct storage access)
```

**Key differentiators for resume** (all implemented and tested):
1. **Model/storage decoupling**: Contract defines WHAT, Binding defines WHERE, Query Service is the only HOW.
2. **Deterministic evidence chain**: Every property maps to a specific dataset column with provenance traceable to the profile that generated it.
3. **Unified read boundary**: REST, Agent tools, future MCP all go through the same permission-isolated query service.
4. **Activation gate**: Nothing goes to pilot without passing binding validation + smoke query.
5. **Zero-DSL query**: JSON equality filters only — no SQL, no custom language, no AST.
6. **Provenance over power**: Every query result includes full package/dataset/binding provenance without leaking data.

**Architecture diagram to prepare** (for portfolio):
```
┌──────────┐    ┌──────────┐    ┌───────────┐    ┌──────────┐
│ Dataset  │───▶│ Modeling │───▶│  Human    │───▶│  Quality │
│ Upload + │    │  Drafts  │    │  Review   │    │  Gate +  │
│ Profile  │    │(generate)│    │(accept/   │    │ Package  │
│          │    │          │    │ reject)   │    │  Build   │
└──────────┘    └──────────┘    └───────────┘    └────┬─────┘
                                                      │
                                                      ▼
┌──────────┐    ┌──────────┐    ┌───────────┐    ┌──────────┐
│ Agent /  │◀───│  Unified │◀───│Dataset    │◀───│ Business │
│MCP (fut) │    │  Query   │    │Binding    │    │ Contract │
│          │    │ Runtime  │    │(generate) │    │ (export) │
└──────────┘    └──────────┘    └───────────┘    └──────────┘
```

**Do NOT put in resume**: MCP runtime, Graph RAG, temporal/time-travel engine, custom query language (SPL/DSL), automatic schema discovery, multi-tenant SaaS, Kubernetes. These are either NOT implemented or explicitly rejected as design decisions.

**Resume-ready capability list** (all tested and verified):
- JWT auth + BCrypt + refresh token rotation + group RBAC
- Document ingestion (MD/TXT/PDF/DOCX) + chunked upload + resumable sessions
- Keyword + semantic (pgvector) hybrid retrieval with group_id isolation
- Citation-grounded RAG with confidence, knowledge gaps, next steps, audit
- Controlled Agent orchestration (FSM, tool registry, HITL, audit)
- Ontology governance (entities, relations, wikilink extraction, validation issues)
- Triage + curation backlog (deterministic rules, not LLM)
- Modeling drafts v1 (Object/Property/Link/Action types, human review)
- Quality-gated immutable contract packages (content hash, versioned, semantic_hash)
- Business pilot five-stage pipeline (goal→data→model→validate→pilot)
- Dataset upload + metadata-first profiling (CSV/XLSX, PK/FK detection, PII masking)
- Dataset→Ontology draft bridge (deterministic generation, evidence privacy)
- Project-scoped package + contract API (WARN override, cross-project isolation)
- **Ontology Dataset Binding (explicit property→column mapping)**
- **Unified read-only query runtime (equality filters, type conversion, provenance)**
- **Pilot activation gate (binding validation + smoke query)**

## Future ECC Prompt

```text
/ecc plan

你正在 F:\semantic-lighthouse 项目中工作。本轮目标是推进【未来阶段：求职展示与项目叙事】。请先不要写代码。

请先阅读：
1. CLAUDE.md
2. README.md
3. docs/agent-handoff.md
4. docs/project-roadmap.md
5. docs/engineering-memory/interview-stories.md
6. docs/engineering-memory/highlight-log.md
7. docs/engineering-memory/pitfall-log.md
8. docs/engineering-memory/portfolio-backlog.md

本阶段目标：
把语义灯塔整理成一个能用于实习求职展示的工程项目，而不是只停留在代码仓库。

启动前请先判断：
1. 当前项目是否已经达到可以展示的完整度。
2. 哪些能力已经真实跑通并测试过。
3. 哪些能力还不能写进简历。
4. 是否存在夸大项目能力的风险。

请围绕以下方向做计划：
1. README 升级：项目定位、架构图、核心链路、本地运行、测试、云端部署。
2. Demo 脚本：权限隔离、文档入库检索、RAG 咨询回答。
3. 简历材料：只写真实跑通并测试过的能力。
4. 面试叙事：每个亮点都对应真实工程问题、风险、方案、指标和结果。

请输出最小可交付计划，必须包含：
- README 应该怎么改
- Demo 应该准备哪些输入和输出
- 哪些能力可以写进简历
- 哪些能力暂时不能写进简历
- 需要补哪些截图、命令、示例
- 学习复盘如何安排
- 验收标准

要求：
- 不夸大项目能力
- 不写未实践技术栈
- 不把“用了很多框架”当亮点
- 重点突出权限隔离、检索质量、RAG 可信度、工程判断力
```
