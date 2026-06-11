# Semantic Lighthouse — 2026-06-11/12 工程日志

## 总览

两个工作日，三轮迭代。从 V2.2 上传链路修复开始，交付 V3.4 ETL 异步摄取管道，再经过回顾审查修复 6 个 P1/P2 级 bug。测试 40→55，migration 0005→0006，ruff 零错误。

---

## 迭代一：V2.2 上传链路工程风险修复

**起点**：40 测试，`0005_v22_chunked_uploads` (head)

**风险**（来自 agent-handoff.md）：
- 上传 chunk 临时文件从不清理
- hash mismatch / 解析失败后合并文件残留
- `read_bytes()` 全量加载内存风险
- GET upload session Member 可看但操作需 Owner/Admin（权限不对称）

**修复**（+6 测试）：
- `verify_file_hash()` — 流式 SHA-256，64KB 分块，O(1) 内存
- `cleanup_upload_temp_dir()` + `cleanup_merged_file()` — 成功/hash失败/解析失败三条清理路径
- GET upload session 从 Member 收紧为 Owner/Admin
- `status = "completing"` 竞态锁
- 过期 session 清理

**结果**：46 passed, 1 warning

---

## 迭代二：V3.4 文档 ETL 消化流水线

**架构决策**：
- 不用 RabbitMQ/Kafka：DB 表做 job queue，2 GiB ECS 零新依赖
- 不用 Elasticsearch：pgvector + ILIKE 已覆盖两种搜索
- FastAPI BackgroundTasks 等价于 Spring `@TransactionalEventListener(AFTER_COMMIT)`
- HNSW index 本轮添加：`m=16, ef_construction=200`，适合 <1M 向量

**交付**（+8 测试）：
- `ingestion_jobs` 表 + `Document.ingestion_error` / `processed_at`
- `document_etl.py` — 7 步管道：Extract→Parse→Clean→Chunk→Embedding→Load→Finalize
- 结构感知切片：heading→段落→句子→硬拆分，配置化 min/max/target/overlap
- 3 个 ingestion job API，启动恢复，search/RAG 过滤 `status=ready`

**审查发现**：代码审查找到 6 个问题，进入迭代三。

---

## 迭代三：V3.4 加固（P1/P2 修复）

| ID | 严重度 | 问题 | 为何测试没抓到 |
|----|--------|------|----------------|
| P1-1 | CRITICAL | PostgreSQL 路径 `PGVECTOR_DIMENSION` NameError | SQLite fallback 绕过 pgvector 代码 |
| P1-2 | CRITICAL | `EmbeddingError` 绕过 3 次 retry | 无失败路径测试 |
| P1-3 | HIGH | 手动 retry 破坏 ready 文档 | 无 ready→retry→fail 测试 |
| P2-1 | HIGH | `step_log` 原地修改不入库 | 无 DB reload 断言 |
| P2-2 | MEDIUM | 测试断言 `in (...)` 让失败也通过 | — |
| P2-3 | INFO | ETL 范围未文档化 | — |

**修复**（+1 测试，ruff 零错误）：
- P1-1：`_PGVECTOR_DIMENSION` → public，显式 import
- P1-2：移除 `except EmbeddingError: return`，异常传播到 retry 循环
- P1-3：`was_ready` 标记，失败恢复 ready，只 fail job
- P2-1：`MutableDict.as_mutable(JSON)` + dict 替换
- P2-2：收紧所有断言为精确匹配
- P2-3：README 加 V3.4 Scope，注明 ETL 仅覆盖分片上传 complete

**并行修复**：
- `on_event` → `lifespan`（消除 110 个 deprecation warning）
- `_snippet` + `_validate_pgvector_dimension` → `routers/_shared.py`
- `_merged_heading()` 修复 chunk 合并 heading_path
- 魔法数字命名 + 测试 SQLite → file-backed

**最终状态**：55 passed, 1 warning, ruff clean, `0006` (head)

---

## 关键工程教训

1. **SQLite 测试绿 ≠ PostgreSQL 可用** — dialect 特定代码路径需要独立的 smoke gate
2. **Retry loop 内层 `except...return` 是 retry killer** — 每步都应传播异常
3. **重试不能比原操作更危险** — ready 文档需要 fallback，新版本只在完全成功后替换
4. **ORM JSON 原地修改不可靠** — SQLAlchemy 需要 `MutableDict` 或显式替换
5. **`in (...)` 断言是假安全感** — 精确断言才能区分成功和失败路径
