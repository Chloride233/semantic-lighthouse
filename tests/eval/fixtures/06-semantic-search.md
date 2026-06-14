---
title: 企业级语义搜索设计
documentType: technical-guide
entityType: Concept
source: semantic-lighthouse-eval
status: published
---

# 企业级语义搜索设计

语义搜索超越关键词匹配，通过理解查询意图和文档语义提高检索质量。

技术：向量化模型映射高维空间，pgvector是PostgreSQL原生扩展，HNSW索引加速近似最近邻搜索。混合策略合并关键词和语义结果去重排序。评测用Recall@k和MRR指标。
