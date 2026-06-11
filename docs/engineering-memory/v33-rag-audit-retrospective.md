# V3.3 RAG Audit Retrospective

## Decision: persist every successful RAG answer

V3.3 adds `rag_runs`.

- Risk if ignored: A generated answer disappears after the HTTP response, making it hard to debug, evaluate, or explain what evidence was used.
- Control: Persist question, answer, confidence, retrieval method, model, citations, knowledge gaps, next steps, user ID, group ID, and timestamp.
- Verification: Tests cover run persistence, replay detail, and non-member rejection.
- Interview version: I made RAG answers auditable, not just interactive.

## Decision: store citations as JSON snapshots

RAG runs store citation snapshots instead of only storing chunk IDs.

- Risk if ignored: Later document edits could change what a past answer appears to have cited.
- Control: Save the citation fields that were returned at answer time.
- Verification: Run detail returns the original citation title, source path, snippet, score, and retrieval method.
- Interview version: For audit and evaluation, the system needs the evidence snapshot used at generation time.

## Decision: group membership still protects audit history

Run history is scoped by `group_id`.

- Risk if ignored: RAG history can leak sensitive questions and cited internal knowledge.
- Control: `/rag/runs` and `/rag/runs/{run_id}` require group membership and query `RagRun.group_id == group_id`.
- Verification: Tests prove an outsider cannot list or read another group's RAG run.
- Interview version: I treated historical answers as protected enterprise data, not harmless logs.
