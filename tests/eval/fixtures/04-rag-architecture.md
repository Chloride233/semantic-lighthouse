---
title: RAG检索增强生成技术架构
documentType: technical-guide
entityType: Concept
source: semantic-lighthouse-eval
status: published
---

# RAG检索增强生成技术架构

RAG将信息检索与LLM结合，基于企业私有知识库生成准确可溯源的回答。

架构：文档入库管道（上传解析分块向量化索引），检索模块（关键词ILIKE语义向量余弦混合），回答生成（LLM引用），可信度评估。关键技术：pgvector HNSW索引、混合检索加权去重、引用守卫防编造。
