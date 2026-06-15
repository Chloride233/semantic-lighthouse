# Claude Code Prompt - RAG Quality Review 2026-06-15

你正在接管 `F:\semantic-lighthouse` 项目。

## 本轮任务名称

P1：真实知识库导入与 DeepSeek RAG 问答质量验收

请注意：  
这不是新增功能任务，而是一次工程验收任务。目标是验证当前系统是否真正完成了：

```text
真实知识库导入 -> 检索 -> RAG 生成 -> 引用追溯 -> 可信度判断 -> 审计落库
```

## 当前已知状态

1. 项目已经有认证、群组、文档、ETL、向量检索、RAG、Conversation、Agent 基础能力。
2. 前端中文体验版已经可用。
3. 最近一次完整测试基线为：
   - `scan_encoding.py` 通过
   - `verify_ui.py` 13/13 passed
   - `pytest` 全量 125 passed
   - Alembic head = `0009_v9_rag_audit`
4. 我已经把 DeepSeek 配置写入 Windows 用户级环境变量。
5. 不要再问我要 `DEEPSEEK_API_KEY`。
6. 不要把任何 API Key、Token、Cookie、密码写入文件、日志、报告或 git commit。
7. `scripts/start_local_preview.ps1` 会强制设置 `CHAT_PROVIDER=fake`，不要用它测试真实 DeepSeek。

## 本轮最高优先级

验证真实 DeepSeek + 真实 ontology 知识库下，RAG 回答是否可信、可追溯、可解释。

## 一、必须先读的文件

开始前请依次阅读：

1. `CLAUDE.md`
2. `README.md`
3. `docs/agent-handoff.md`
4. `docs/project-roadmap.md`
5. `docs/CODEMAPS/architecture.md`
6. `docs/CODEMAPS/backend.md`
7. `docs/CODEMAPS/data.md`
8. `docs/engineering-memory/plan-rag-quality-review-2026-06-15.md`
9. `docs/engineering-memory/pitfall-log.md`
10. `docs/engineering-memory/highlight-log.md`

读完后先输出：

1. 当前项目状态判断
2. 本轮验收目标
3. 你认为不能碰的范围
4. 你准备运行的命令
5. 如果 DeepSeek 不可用，你的处理策略

不要一上来改代码。

## 二、严格禁止事项

本轮禁止：

1. 不要引入 Elasticsearch。
2. 不要引入 MinIO。
3. 不要引入 RabbitMQ、Kafka、Celery。
4. 不要引入 Kubernetes。
5. 不要引入新的 Agent Framework。
6. 不要重构认证系统。
7. 不要重构群组权限。
8. 不要重构上传协议。
9. 不要做新前端大改版。
10. 不要修改项目定位和路线图。
11. 不要写简历叙事。
12. 不要删除已有测试来让结果通过。
13. 不要把 fake provider 的结果伪装成真实 DeepSeek 结果。
14. 不要把 Key 写进 `.env.example`、文档、测试、日志、提交信息。
15. 不要在报告中输出完整 API Key。

允许做的事：

1. 修复 RAG 输出契约 bug。
2. 修复 citation 字段缺失或不可追溯问题。
3. 修复 confidence 明显不合理的问题。
4. 修复前端展示误导用户的问题。
5. 增加 RAG 质量验收脚本。
6. 增加测试。
7. 更新工程记忆和交接文档。
8. 如果 DeepSeek 调用失败，可以记录失败原因，但不能悄悄切 fake 当作真实结果。

## 三、第一步：确认 DeepSeek 配置

必须先运行：

```powershell
.\.venv\Scripts\python -X utf8 -c "from semantic_lighthouse.config import get_settings; s=get_settings(); print('provider=', s.chat_provider); print('model=', s.chat_model); print('key_set=', bool(s.deepseek_api_key))"
```

期望结果：

```text
provider= deepseek
model= deepseek-chat
key_set= True
```

如果不是这个结果：

1. 停止后续 DeepSeek 验收。
2. 输出实际结果。
3. 说明原因。
4. 不要自己编 Key。
5. 不要改代码绕过。
6. 可以继续做 fake provider 的 pipeline 验收，但必须在报告中明确标注“DeepSeek 未验证”。

## 四、第二步：检查工作区和基线

运行：

```powershell
git status --short
```

如果 working tree 不干净：

1. 先列出改动。
2. 判断是计划文件/文档改动还是代码改动。
3. 不要覆盖用户改动。
4. 必要时先暂停并说明。

然后运行基线：

```powershell
.\.venv\Scripts\python scripts\scan_encoding.py
.\.venv\Scripts\python scripts\verify_ui.py
.\.venv\Scripts\python -m pytest -q --tb=short --basetemp .tmp\pytest-full
```

如果基线失败：

1. 先定位失败原因。
2. 不要继续 RAG 验收。
3. 只修最小必要问题。
4. 修复后重新跑基线。

## 五、第三步：确认真实知识库路径

检查当前配置中的知识库路径：

```powershell
.\.venv\Scripts\python -X utf8 -c "from semantic_lighthouse.config import get_settings; s=get_settings(); print(s.knowledge_base_path)"
```

然后确认路径存在，并统计 Markdown 文件数量。

要求：

1. 默认路径应是 `F:\ontology-kb\knowledge-graph`。
2. 如果路径不存在，不要改代码硬编码。
3. 如果路径存在，抽查至少 5 个代表性文件：
   - ontology
   - ai-transformation-roadmap
   - graph-rag 或 RAG 相关
   - knowledge-graph
   - data governance / master data / methodology 相关

记录：

- 文件路径
- frontmatter 是否存在
- 是否包含标题
- 是否包含 Obsidian wikilink
- 是否适合作为 RAG 证据来源

## 六、第四步：执行真实知识库导入

使用当前系统能力完成导入，不要绕过业务逻辑直接写数据库。

推荐路径：

1. 通过 API 注册/登录测试用户。
2. 创建测试工作区。
3. 调用：
   `POST /groups/{group_id}/documents/import-local`
4. 确认返回：
   - `imported_count > 0`
   - `skipped_count` 合理
5. 查询文档列表，确认文档进入系统。
6. 如果 ETL 是异步，等待或触发直到 ready。
7. 确认 ready 文档数量 > 0。
8. 确认 `document_chunks` 数量 > 0。

必须记录：

- `group_id`
- `imported_count`
- `skipped_count`
- `documents_count`
- `ready_count`
- `chunks_count`

不要记录 token。

## 七、第五步：检索与 RAG 验收问题集

必须测试以下 10 个问题：

1. 企业为什么需要 Ontology？
2. Ontology 和数据中台有什么区别？
3. 企业 AI 转型第一阶段应该做什么？
4. RAG 为什么需要引用来源？
5. 知识图谱和 Ontology 有什么区别？
6. 企业 AI 项目为什么不能只靠大模型？
7. 数据治理和 AI 转型有什么关系？
8. 什么情况下应该低可信回答？
9. Agent 为什么需要受控工具调用？
10. 如何判断企业是否适合先做 RAG？

每个问题必须记录：

- question
- retrieval_method
- retrieved_count
- citations_count
- actual citation titles
- actual citation source_path
- confidence
- answer 是否中文
- answer 是否泄露 prompt/template
- answer 是否包含明显英文模板，例如：
  - `Based on retrieved sources`
  - `according to the provided context`
  - `Review the cited chunks`
- knowledge_gaps 是否合理
- next_steps 是否合理
- rag_run_id
- rag_run 是否能回放
- audit 字段是否完整
- 是否通过
- 失败原因

## 八、RAG 质量判断标准

一个问题算通过，必须满足：

1. 返回 200。
2. answer 是中文。
3. answer 是咨询式回答，不是调试文本。
4. 不泄露 prompt。
5. 不出现英文模板。
6. `citations_count >= 1`，除非确实是无证据问题。
7. citation 中必须包含：
   - `document_id`
   - `chunk_id`
   - `title`
   - `source_path`
   - `snippet`
   - `retrieval_method` 或 `score`
8. confidence 只能是 `high` / `medium` / `low`。
9. confidence 与证据数量大致一致：
   - 没有 citation 时必须 low
   - citation 很少或明显不相关时不应 high
10. knowledge_gaps 不能是空泛废话。
11. next_steps 应该能指导下一步咨询动作。
12. rag_run 必须落库。
13. rag_run 能通过 API 查询或数据库查询追溯。
14. 非成员不能访问该 group 的 rag_run。

如果这些标准不满足，必须记录为问题。

## 九、DeepSeek 真实调用要求

如果 DeepSeek 可用：

1. 本轮至少 10 个问题都用真实 DeepSeek 跑一遍。
2. 不要只跑 fake。
3. 记录模型名。
4. 记录 `duration_ms`。
5. 记录 `error_message`，如果失败。
6. 如果某个问题 DeepSeek 失败，不要自动改用 fake 盖过去。
7. 如果 DeepSeek 返回非 JSON 或结构不符合要求，要记录为模型输出契约问题。

如果 DeepSeek 不可用：

1. 明确写入报告：DeepSeek 未完成真实验收。
2. 可以继续用 fake 验证 pipeline。
3. fake 结果不能写成“真实回答质量通过”。

## 十、如果发现 bug，处理方式

发现 bug 后按这个顺序：

1. 写清楚现象。
2. 定位根因。
3. 判断是否属于本轮范围。
4. 如果属于，做最小修复。
5. 增加或修改测试。
6. 跑相关测试。
7. 记录到 pitfall-log 或 rag-quality-review。

不要顺手重构。

常见可能问题：

- citation 缺字段
- answer 泄露 prompt
- confidence 全是 high
- 无证据也强答
- rag_run 没落库
- 前端 score 显示误导
- DeepSeek 返回 JSON 格式不稳定
- ontology wikilink 被当作普通文本影响回答
- 文档未 ready 就参与检索
- 非成员可访问历史 run

## 十一、报告文件要求

最终报告写入：

```text
docs/engineering-memory/rag-quality-review-2026-06-15.md
```

报告结构必须包含：

```markdown
# RAG Quality Review - 2026-06-15

## 1. Summary
- 是否完成真实 DeepSeek 验收
- 是否完成真实知识库导入
- 总体结论

## 2. Environment
- chat_provider
- chat_model
- deepseek_key_set: true/false
- knowledge_base_path
- imported_count
- ready_count
- chunks_count

## 3. Baseline Commands
列出实际运行命令和结果。

## 4. Question Review Table
| # | Question | Retrieved | Citations | Confidence | Chinese | Prompt Leak | Audit | Pass | Notes |
|---|---|---|---|---|---|---|---|---|---|

## 5. Findings
### Finding 1
- severity
- symptom
- root cause
- fix / decision
- verification

## 6. Risks
- 仍然存在的风险
- 暂不处理原因

## 7. Next Actions
- 下一轮最小任务
```

## 十二、交接文档更新

更新：

```text
docs/agent-handoff.md
```

必须写清：

1. 本轮验收是否完成。
2. DeepSeek 是否真实可用。
3. 导入了多少真实文档。
4. RAG 质量结论。
5. 当前最大风险。
6. 下一步建议。

如果有踩坑，更新：

```text
docs/engineering-memory/pitfall-log.md
```

如果有工程亮点，更新：

```text
docs/engineering-memory/highlight-log.md
```

## 十三、最终验证命令

完成后必须运行：

```powershell
.\.venv\Scripts\python scripts\scan_encoding.py
.\.venv\Scripts\python scripts\verify_ui.py
.\.venv\Scripts\python -m pytest -q --tb=short --basetemp .tmp\pytest-full
```

如果修改了 migration 或模型：

```powershell
$dbPath = "F:\semantic-lighthouse\.tmp\rag-quality-migration.db"
New-Item -ItemType Directory -Force -Path "F:\semantic-lighthouse\.tmp" | Out-Null
if (Test-Path $dbPath) { Remove-Item $dbPath -Force }
$env:DATABASE_URL = "sqlite+pysqlite:///" + $dbPath.Replace("\","/")
.\.venv\Scripts\python -m alembic upgrade head
.\.venv\Scripts\python -m alembic current
```

## 十四、提交要求

如果有代码改动，按最小边界 commit。

建议 commit 类型：

```text
test: add rag quality review coverage
fix: improve rag answer contract
docs: record rag quality review
```

不要把多个不相关改动塞进一个 commit。

如果只有文档，也要单独 commit。

## 十五、完成后输出

完成后请输出：

1. DeepSeek 配置检测结果
2. 是否使用真实 DeepSeek 完成 10 问验收
3. 真实知识库导入结果
4. 10 个问题验收汇总表
5. 发现的问题
6. 做过的修复
7. 运行过的命令和结果
8. 更新过的文档
9. commit hash
10. 下一步建议

现在开始。先读文件和跑 DeepSeek 配置检测，不要直接改代码。
