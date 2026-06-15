# P1: 真实知识库导入与 RAG 问答质量验收 — 执行计划

**日期**: 2026-06-15  
**版本**: Project Phase 3 hardening  
**分支**: master (clean)

---

## 1. 当前状态判断

### 1.1 已验证基线 ✅

| 检查项 | 结果 |
|--------|------|
| Git status | Clean (`master`, nothing to commit) |
| `scripts/scan_encoding.py` | OK — 无编码问题 |
| `scripts/verify_ui.py` | 13/13 passed |
| `pytest -q --tb=short` | **125 passed**, 2 warnings (非代码问题) |
| Alembic migration | `0009_v9_rag_audit` at head, 17 tables |
| Ruff check | All checks passed |

### 1.2 真实知识库状态

- `KNOWLEDGE_BASE_PATH` 默认值: `F:\ontology-kb\knowledge-graph`
- **路径存在**: ✅
- **内容**: INDEX.md + schema.md + AUTO_INDEX.md + 7 个子目录 (concepts/, methodologies/, vendors/, products/, persons/, cases/, faqs/, proposals/, research/)
- **实体数**: 77 个 Obsidian 格式 Markdown 实体
- **格式**: YAML frontmatter + Obsidian wikilinks (`[[...]]`)
- **覆盖领域**: 完全覆盖本轮 10 个验收问题

### 1.3 运行环境关键事实

- **无 `.env` 文件** → 所有配置使用默认值
- **`chat_provider` 默认 = `deepseek`**，但 `DEEPSEEK_API_KEY` 未设置
- **后果**: 真实 DeepSeek RAG 调用会抛出 `ChatError`
- **`embedding_provider` 默认 = `aliyun`**，但 `DASHSCOPE_API_KEY` 未设置
- **当前测试可用 `chat_provider=fake`** (确定性输出，验证 pipeline 契约)

### 1.4 核心判断

- 测试基础设施健康，可安全执行本轮任务
- **无 API Key 时**，fake provider 可验证检索质量 + 引用契约 + 落库完整性，但无法验证 LLM 生成质量
- **有 API Key 时**，可做完整 RAG 质量验收

---

## 2. 本轮最小计划

### Phase A: 真实知识库导入

| # | 步骤 | 验证方式 |
|---|------|----------|
| A1 | 确认 KNOWLEDGE_BASE_PATH 配置策略 | 读 config.py → 确认默认值 + env 覆盖 |
| A2 | 评估 ontology 文件兼容性 (wikilinks, frontmatter) | 抽查 5 个代表文件 |
| A3 | 确定导入范围 | 全部 77 个文件，分批导入 |
| A4 | 通过 `POST /import-local` 导入 | 确认 imported_count > 0, status=ready |
| A5 | 验证检索可用 | keyword/hybrid 已知关键词查询 |

### Phase B: Chat Provider 策略

| 方案 | 可用性 | 能验证什么 | 不能验证什么 |
|------|--------|-----------|-------------|
| **fake** | ✅ 无需 Key | 检索质量、citation 契约、落库、中文输出 | LLM 生成质量 |
| **deepseek** | ❌ 需 DEEPSEEK_API_KEY | 完整 RAG 质量 | — |

**推荐**: 先 fake 验证完整 pipeline，如有 Key 再 deepseek 验证回答质量。

### Phase C: RAG 质量验收 — 10 个问题

对每个问题记录: question / expected doc / actual citations / confidence / 是否中文 / 是否泄露 prompt / citations 可追溯性 / 发现的问题

| # | 问题 | 期望关联文档 |
|---|------|-------------|
| Q1 | 企业为什么需要 Ontology？ | concepts/ontology.md |
| Q2 | Ontology 和数据中台有什么区别？ | concepts/ontology.md, concepts/data-integration.md |
| Q3 | 企业 AI 转型第一阶段应该做什么？ | methodologies/ai-transformation-roadmap.md |
| Q4 | RAG 为什么需要引用来源？ | concepts/graph-rag.md |
| Q5 | 知识图谱和 Ontology 有什么区别？ | concepts/knowledge-graph.md, concepts/ontology.md |
| Q6 | 企业 AI 项目为什么不能只靠大模型？ | concepts/ontology.md, concepts/graph-rag.md |
| Q7 | 数据治理和 AI 转型有什么关系？ | concepts/master-data-management.md, methodologies/ai-transformation-roadmap.md |
| Q8 | 什么情况下应该低可信回答？ | concepts/graph-rag.md |
| Q9 | Agent 为什么需要受控工具调用？ | concepts/mcp.md, concepts/action-type.md |
| Q10 | 如何判断企业是否适合先做 RAG？ | methodologies/ai-transformation-roadmap.md, concepts/graph-rag.md |

### Phase D: Bug 修复 (如有)

**允许**: RAG 输出契约 bug / citation 不准确 / confidence 不合理 / 前端展示问题 / eval 脚本 / 测试  
**不允许**: 新功能 / 新中间件 / 认证权限上传重构 / 删除已有测试

### Phase E: 文档更新

1. `docs/engineering-memory/rag-quality-review-2026-06-15.md` — 验收报告
2. `docs/agent-handoff.md` — 更新状态
3. `docs/engineering-memory/pitfall-log.md` 或 `highlight-log.md` — 按需

### Phase F: 最终验证

`scan_encoding.py` + `verify_ui.py` + `pytest` 全量 + Alembic 迁移 (如有改动)

---

## 3. 准备跑的命令

```bash
# Phase A: 导入
# 1. 检查文件数量
find "F:/ontology-kb/knowledge-graph" -name "*.md" | wc -l

# 2. 抽查文件兼容性
head -30 "F:/ontology-kb/knowledge-graph/concepts/ontology.md"

# 3. 通过 API 导入 (通过 pytest 脚本或直接 API 调用)
# 使用 chat_provider=fake 环境

# Phase C: 验收
# 4. 运行验收脚本
.venv/Scripts/python.exe scripts/run_eval.py

# 5. 跑 RAG 专项测试
.venv/Scripts/python.exe -m pytest tests/test_rag.py tests/test_eval.py -v --tb=short

# Phase F: 最终验证
.venv/Scripts/python.exe scripts/scan_encoding.py
.venv/Scripts/python.exe scripts/verify_ui.py
.venv/Scripts/python.exe -m pytest -q --tb=short
```

---

## 4. 不能碰的范围

| 范围 | 原因 |
|------|------|
| 认证 / 权限 / 上传协议 | 明确禁止 (除非阻断性 bug) |
| Elasticsearch / MinIO / RabbitMQ / Celery | 不引入新中间件 |
| 复杂 Agent Framework | 不新增功能 |
| 新模型供应商 | 不上新对接 |
| 云部署 | 不上云 |
| 前端大改版 | 不做新 UI |
| 项目定位 / 路线图 | 不改方向 |
| API Key / Token / 密码提交 | 安全红线 |
| 删除已有测试 | 不以删代修 |
| wikilinks 作为纯文本 | 已知限制，不修 |

---

## 5. 预计验收标准

### 5.1 必须通过

- [ ] 125+ pytest 全部通过 (不减少)
- [ ] `scan_encoding.py` 通过
- [ ] `verify_ui.py` 13/13 通过
- [ ] Alembic migration 在 head
- [ ] Ruff check 干净
- [ ] 真实知识库文档成功导入 (imported_count > 0)
- [ ] 10 个验收问题全部有 RAG 响应记录
- [ ] 每个问题的 audit 字段完整 (status, duration_ms, retrieved_count, citations)
- [ ] 验收报告写出

### 5.2 合同级验收 (与 Provider 无关)

- [ ] RAG answer 不含英文模板短语
- [ ] Confidence 在 {high, medium, low} 范围
- [ ] Citations 包含 document_id, chunk_id, title, snippet, score, retrieval_method
- [ ] run_id 可追溯 (GET /runs/{run_id})
- [ ] 无 citation 时 confidence=low, model="local-evidence-gate"
- [ ] 前端不显示裸枚举值 / falsy fallback

### 5.3 如有 API Key

- [ ] DeepSeek 返回结构化 JSON
- [ ] 回答体现检索到的具体文档内容
- [ ] knowledge_gaps 和 next_steps 有意义

---

## 6. 已知风险

| 风险 | 概率 | 影响 | 应对 |
|------|------|------|------|
| Obsidian wikilinks 显示为 `[[...]]` | 高 | 低 | 记录为已知限制 |
| 中文 ILIKE 检索可能粗糙 | 中 | 中 | hybrid 模式补偿 |
| Fake provider 答案泛化 | 确定 | 中 | 区分 contract vs 生成质量验收 |
| ontology frontmatter aliases 字段 | 低 | 低 | 检查 parse_markdown 行为 |
