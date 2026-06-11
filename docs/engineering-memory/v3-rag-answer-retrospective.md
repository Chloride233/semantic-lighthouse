# V3 RAG Answer Retrospective

## Decision: generation is a separate step after retrieval

V3 adds a RAG answer endpoint without changing the V2 document and vector schema.

- Risk if ignored: Calling an LLM directly can bypass retrieval quality and permission boundaries.
- Control: The answer endpoint first checks group membership, retrieves only `group_id`-scoped chunks, then sends citation snippets to the chat provider.
- Verification: Tests cover member access, non-member rejection, and cross-group citation isolation.
- Interview version: I treated LLM generation as the last step in a controlled pipeline, not as a replacement for authorization and retrieval.

## Decision: fake chat provider in tests

Tests use a deterministic fake chat provider.

- Risk if ignored: Unit tests would depend on a real API key, network availability, external model behavior, and token cost.
- Control: `CHAT_PROVIDER=fake` keeps tests local while preserving the same endpoint contract.
- Verification: RAG tests validate response shape, citations, confidence, and error behavior.
- Interview version: I separate provider integration smoke tests from regression tests so the core system remains testable offline.

## Decision: answer output is structured

The RAG endpoint returns `answer`, `confidence`, `knowledge_gaps`, `next_steps`, and `citations`.

- Risk if ignored: A plain text answer is hard to audit and hard to use for consulting handoff.
- Control: The chat prompt asks for strict JSON, and provider output is validated before returning to the API caller.
- Verification: Tests assert citation fields and structured response fields.
- Interview version: For an enterprise AI consultant agent, the user needs both the recommendation and the evidence boundary behind it.

## Decision: V3 remains single-turn

V3 does not add Agent memory, tools, or multi-turn orchestration.

- Risk if ignored: Adding Agent behavior before RAG answer quality is stable would make failures harder to debug.
- Control: V3 only proves the single-turn retrieval-to-answer loop.
- Verification: The API is small enough to test with existing auth, document, and embedding fixtures.
- Interview version: I deliberately built a dependable RAG answer chain before adding autonomy.

## Decision: no retrieved evidence means no LLM call

V3.1 adds a local evidence gate.

- Risk if ignored: The chat model may generate a fluent answer even when retrieval found no supporting context.
- Control: If retrieval returns no citations, the API returns a low-confidence answer with knowledge gaps and does not call the chat provider.
- Verification: Tests prove a DeepSeek-configured request with no retrieved evidence returns `model=local-evidence-gate` instead of failing on a missing API key.
- Interview version: I added a refusal/deferral path because enterprise RAG should know when not to answer.

## Decision: keyword RAG should not match only the full question

V3.1 adds lightweight query planning for keyword RAG.

- Risk if ignored: A natural customer question like “我们已经有数据中台，为什么还需要 Ontology？” will not match documents unless the whole sentence appears verbatim.
- Control: Extract a small set of Chinese and English terms, then search chunk content, document title, and source path.
- Verification: Tests prove a mixed Chinese-English question can retrieve an `Ontology` document through keyword RAG.
- Interview version: I learned that retrieval quality is not only about vector databases; query planning also determines whether the system can find evidence.
