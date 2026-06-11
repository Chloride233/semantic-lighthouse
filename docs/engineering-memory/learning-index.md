# Learning Index

This file summarizes the project owner's current learning map. It should point to detailed learning-review files rather than replacing them.

## Concepts Already Practiced

- JWT access token: useful for short-lived, stateless authentication and lower per-request database cost.
- Access token lifetime: 15 minutes limits the damage window if a token leaks.
- Refresh token: a longer-lived credential used to get a new access token without forcing full login every 15 minutes.
- httpOnly cookie: protects refresh tokens from common JavaScript-based theft paths.
- Refresh token rotation: each refresh invalidates the old token and creates a new one.
- Token family replay detection: reuse of an old refresh token indicates possible theft and should revoke the family.
- BCrypt password hashing: stores irreversible password hashes instead of plaintext passwords.
- Role-based group permission: Owner/Admin/Member boundaries protect write operations and administration.
- `group_id` data isolation: the final SQL-level boundary that prevents cross-group document, chunk, retrieval, and RAG leakage.
- Chunking: turns documents into smaller retrieval units so search and RAG context stay explainable and bounded.
- Idempotency: repeating the same operation should not create duplicated business state.
- Citation fields: search and RAG results need source fields for traceability and audit.
- RAG confidence and knowledge gaps: enterprise users need to know how well-supported an answer is.

## Weak Points To Keep Training

- Upload cleanup: how to remove temp chunks and failed merged files without deleting valid originals.
- Memory control: why full-file reads and parser behavior matter on a 2 GiB server.
- Production deployment checks: how env files, Docker Compose, migrations, health checks, and security groups interact.
- PDF/DOCX parsing boundaries: what is supported, what is not, and how that affects answer quality.
- Retrieval evaluation: how to judge recall, precision, citation quality, and no-evidence behavior.
- Hybrid search and rerank: when keyword plus vector search is needed and what risk it controls.
- Agent memory and multi-turn state: when V4 should add state, what it stores, and how permissions still apply.
- Code review skill: translating test gaps and implementation details into concrete engineering risks.

## Current Learning Review Files

- `docs/engineering-memory/v1-learning-review.md`: auth, token, role, and group-isolation reasoning.
- `docs/engineering-memory/v2-learning-review.md`: document ingestion, chunking, search, citation, and RAG-preparation reasoning.

## Future Update Rule

When a learning Q&A happens, record four parts in the matching learning review:

```md
## QNN: Question title

- Question:
- My answer:
- Engineering answer:
- Gap:
- Interview version:
```

Then update this file if the concept becomes either "practiced" or a known weak point.
