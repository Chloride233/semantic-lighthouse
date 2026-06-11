# V2 Documents Retrospective

## Decision: retrieval foundation before upload infrastructure

V2 focuses on a permission-aware document retrieval loop instead of the full MinIO chunk-upload design.

- Risk if ignored: The project could spend too much effort on file transport before proving that documents can be retrieved safely by group.
- Control: Implement local Markdown import and single Markdown upload only.
- Verification: Tests cover import, upload, search, duplicate import, and cross-group isolation.
- Interview version: I first built the document retrieval boundary that RAG will inherit. Upload reliability can be upgraded later, but retrieval authorization must be correct before RAG exists.

## Decision: PostgreSQL keyword search before vector search

V2 uses PostgreSQL keyword matching for the first searchable document engine.

- Risk if ignored: Introducing embeddings and vector search too early would make failures harder to explain.
- Control: Use simple keyword search to verify chunking, citation fields, and `group_id` filters.
- Verification: Search tests assert returned citation fields and prove one group cannot see another group's chunks.
- Interview version: I delayed vector search until the metadata, chunking, and authorization boundary were measurable. This made the first retrieval version easier to debug and explain.

## Decision: Markdown only

V2 only accepts Markdown files.

- Risk if ignored: PDF/DOCX parsing quality would become a new source of noise before the retrieval pipeline is stable.
- Control: Parse Markdown frontmatter and headings from the existing ontology knowledge base.
- Verification: Tests confirm frontmatter fields and heading-based chunks are stored.
- Interview version: I chose Markdown first because the source knowledge base is already Markdown with structured frontmatter. That lets the system preserve business metadata instead of treating documents as plain blobs.

## Decision: `group_id` on documents and chunks

Both `documents` and `document_chunks` store `group_id`.

- Risk if ignored: A future retrieval query could join incorrectly or search chunks without the group boundary.
- Control: Search and document detail queries filter by `group_id` at the data layer.
- Verification: Tests cover non-member rejection and cross-group search isolation.
- Interview version: I store group scope directly on retrievable chunks because RAG safety depends on the retrieval query, not only on the API controller.
