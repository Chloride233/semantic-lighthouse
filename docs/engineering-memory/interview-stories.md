# Interview Stories

## V1 Candidate Story: Authentication As RAG Safety Infrastructure

Semantic Lighthouse V1 deliberately starts before RAG. The reason is that enterprise RAG cannot be safe if identity and group-level authorization are added later as an afterthought.

The V1 system implements a short-lived Access Token, httpOnly Refresh Token Cookie, refresh token database hashing, token rotation, replay detection, and group roles. This creates a security boundary that V2 document ingestion and V3 retrieval can inherit through group_id filters.

The key engineering judgment is that retrieval authorization is not only an API problem. It must be reflected in the data access layer, otherwise a future query pipeline could accidentally retrieve or cite unauthorized knowledge.

## V2 Candidate Story: Permission-Aware Retrieval Before RAG

Semantic Lighthouse V2 adds the document layer that V3 RAG will depend on. The system imports or uploads Markdown into group-scoped documents and chunks, then searches chunks only inside the requesting user's group.

The important choice is that V2 does not jump straight to vector search. It first proves that document metadata, chunking, citation fields, and group-level retrieval isolation work with a simple PostgreSQL keyword search.

This creates a measurable boundary: a user can only search documents in groups they belong to, and every search result carries the source path and frontmatter metadata needed for later RAG citations.

## V2.1 Candidate Story: Vector Search Without Losing Permission Boundaries

Semantic Lighthouse V2.1 adds semantic retrieval through cloud embeddings and PostgreSQL pgvector, but it keeps `group_id` filtering in the database layer.

The important engineering choice is separating document ingestion from embedding generation. Documents can be imported and searched by keyword even if the cloud embedding provider is unavailable. Embeddings are built through an explicit Owner/Admin operation, which makes retry, failure handling, and cost control easier to explain.

This keeps the system ready for V3 RAG while preserving the project thesis: enterprise AI retrieval must be permission-correct before it is intelligent.
