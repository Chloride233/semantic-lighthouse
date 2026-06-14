---
title: Prompt工程最佳实践
documentType: technical-guide
entityType: Concept
source: semantic-lighthouse-eval
status: published
---

# Prompt工程最佳实践

Prompt工程设计LLM输入以获得高质量输出，好的Prompt显著提升RAG系统回答质量。

核心：明确角色、提供约束、Few-shot示例、列出禁止项。RAG场景：system message设定角色格式，user message含问题和检索上下文，证据不足时明确说明。常见反模式：Prompt过长、英文Prompt处理中文场景。
