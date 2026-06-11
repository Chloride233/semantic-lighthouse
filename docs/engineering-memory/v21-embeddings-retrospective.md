# V2.1 Embeddings Retrospective

## Decision: cloud embedding, local permissions

V2.1 uses a cloud embedding provider but keeps vector storage and permission filtering inside PostgreSQL.

- Risk if ignored: A separate vector service could make `group_id` filtering harder to audit.
- Control: Store chunk embeddings on `document_chunks` and keep semantic search scoped by `DocumentChunk.group_id`.
- Verification: Tests cover semantic search, non-member rejection, and cross-group isolation with a fake provider.
- Interview version: I use cloud embedding for model capability, but keep authorization in my own database layer.

## Decision: manual rebuild instead of import-time embedding

V2.1 does not call the embedding provider during document import.

- Risk if ignored: Cloud API latency or failure could make basic document ingestion unreliable.
- Control: Add a manual rebuild endpoint that Owner/Admin can trigger after documents are imported.
- Verification: Tests prove rebuild can skip existing embeddings and force regeneration when requested.
- Interview version: I separated ingestion from embedding generation so retrieval indexing can fail or retry without corrupting the document corpus.

## Decision: fake provider in tests

Tests use deterministic fake embeddings.

- Risk if ignored: Tests would depend on a real cloud API key, network availability, cost, and model behavior.
- Control: Use `EMBEDDING_PROVIDER=fake` in tests while keeping the same API shape.
- Verification: All API tests run locally without external calls.
- Interview version: I test my integration contract and permission logic locally, and reserve real provider smoke tests for runtime verification.

## Runtime note: pgvector container

V2.1 changes Docker PostgreSQL from `postgres:17` to `pgvector/pgvector:pg17`.

- Current verification: SQLite migration, OpenAPI, compile checks, API tests, PostgreSQL migration, and PostgreSQL-backed semantic search smoke passed.
- Runtime detail: Docker Compose recreated Postgres with `pgvector/pgvector:pg17`, then Alembic upgraded `0002 -> 0003`.
- Risk if ignored: An old `postgres:17` container will not support `CREATE EXTENSION vector`.
- Control: Recreate the local Postgres container with the new image before PostgreSQL-backed smoke testing.

## Pitfall: SQLite tests do not prove pgvector SQL works

Two PostgreSQL-only issues appeared during runtime smoke:

- A raw `literal_column` expression left `:query_vector` unbound in PostgreSQL.
- A pgvector distance expression returned a float but inherited vector result processing until it was explicitly cast to `Float`.

Engineering lesson: database fallback tests are useful, but vector SQL must still be smoke-tested on real PostgreSQL because dialect behavior matters.

## Decision: fixed pgvector dimension with runtime validation

The database schema stores chunk vectors as `vector(1024)`.

- Risk if ignored: Changing `EMBEDDING_DIMENSION` without a migration would make the provider return vectors that cannot be safely stored or searched.
- Control: PostgreSQL rebuild and semantic search validate that runtime `EMBEDDING_DIMENSION` matches the pgvector column dimension.
- Verification: API tests pass with SQLite fake vectors; PostgreSQL-backed semantic smoke passes with dimension 1024.
- Interview version: I made vector dimension a schema decision, not a casual runtime toggle. Changing embedding dimension should be handled as a migration, because pgvector columns are dimension-specific.

## Runtime verification: real Aliyun embedding smoke

The real Aliyun embedding provider was manually smoke-tested from PowerShell.

- Result: one input produced one vector.
- Dimension: 1024.
- Why it matters: The cloud provider output matches the pgvector schema dimension used by V2.1.
- Full chain result: Uploading one Markdown document, rebuilding embeddings with `text-embedding-v4`, and running semantic search succeeded.
- Semantic smoke output: `rebuild 200`, `processed_count: 1`, `semantic 200`, `retrieval_method: semantic`, `score: 0.5807814175123401`, `title: Ontology Smoke`.
- Why it matters: V2.1 is no longer only fake-provider tested; the real cloud embedding to local pgvector retrieval path works on a small sample.
