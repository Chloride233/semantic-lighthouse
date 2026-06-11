# Interview Demo Questions

Use these questions to demonstrate Semantic Lighthouse as an enterprise AI transformation RAG prototype.

## Demo 1: Ontology Value

Question:

```text
企业已经有数据中台，为什么还需要 Ontology？
```

What it demonstrates:

- semantic retrieval over business concepts
- consulting-style answer generation
- citation-backed explanation
- the difference between raw data management and business-semantic context

Expected answer shape:

- explain that data platforms manage raw tables/assets
- explain that Ontology adds business objects, relationships, permissions, and workflow context
- mention that AI retrieval needs business meaning, not only table names
- cite the Ontology source chunk

Engineering point to explain:

> This is not a generic chatbot answer. The system first retrieves group-scoped chunks, then sends only those citation snippets to DeepSeek.

## Demo 2: Permission Boundary

Question:

```text
非本组成员能不能检索或引用其他组的知识库？
```

What it demonstrates:

- V1 group membership boundary
- V2 document and chunk `group_id`
- V3 RAG inherits retrieval permissions
- enterprise data isolation story

Expected answer shape:

- explain non-members cannot access group resources
- explain document/chunk queries include `group_id`
- explain RAG citations come from retrieval results, so generation inherits the same boundary

Engineering point to explain:

> The last line of defense is not the prompt. It is the database query condition and membership check.

## Demo 3: Evidence Insufficient

Question:

```text
请基于当前知识库评估某个未录入供应商的实施成本。
```

What it demonstrates:

- no-evidence gate
- confidence and knowledge-gap reporting
- avoiding hallucination
- consulting trustworthiness

Expected answer shape:

- return low confidence if no citation is retrieved
- list missing knowledge
- suggest adding vendor profile, implementation case, cost assumptions, or delivery constraints

Engineering point to explain:

> A useful enterprise RAG system must know when not to answer. Refusal or deferral is part of answer quality.

## Two-Minute Demo Script

1. Open `/docs` on the ECS public endpoint.
2. Register and login a user.
3. Create a group.
4. Upload a small Markdown knowledge note.
5. Rebuild embeddings.
6. Run semantic search and show citation fields.
7. Run RAG answer and show `answer`, `confidence`, `knowledge_gaps`, `next_steps`, and `citations`.
8. Explain that every document, chunk, search, and RAG call is scoped by `group_id`.

Closing line:

> The project is intentionally not a productized SaaS. It is a focused enterprise RAG/Agent prototype that proves auth, tenant isolation, document ingestion, semantic retrieval, and citation-grounded answer generation.
