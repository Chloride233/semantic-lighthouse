# Interview Stories

## Phase 14.5 — From Ontology Contract to Real Business Object Queries

Semantic Lighthouse Phase 14 established a five-stage business pilot pipeline: goal → data → model → validate → pilot. Phase 14.5 closes the loop by proving that a human-reviewed, quality-gated Ontology contract can read real business objects through explicit DatasetBindings.

The problem: after compiling a business_v1 contract from accepted modeling drafts (Phase 13) and building project-scoped packages with quality gates (Phase 14.4), the contract was a validated JSON artifact — but it had no path to actual data. Users couldn't ask "show me the customers in this dataset" through the contract.

The solution was NOT to build a general data platform, an SQL execution engine, or a custom query DSL. Instead, I built three deterministic components:

1. **OntologyDatasetBinding**: An explicit persistent record connecting each Object Type in a contract package to its source DatasetAsset. Property mappings record exactly which contract property (api_name) maps to which dataset column. No guessing — every mapping traces back to accepted drafts whose evidence_refs record the column name, type, and PK/FK role.

2. **Unified Query Contract**: A single `POST /runtime/query` endpoint that accepts a restricted JSON body — object_type, optional field whitelist, optional equality filters, limit/offset, explain_only. No SQL. No expression strings. No custom language. The query reads CSV or XLSX using the same controlled parsing as dataset profiling, validates the file path stays within the project's storage directory, applies type conversion based on the contract's declared value_types, and returns rows with full provenance metadata.

3. **Pilot Activation Gate**: Before advancing from validate → pilot, the activate endpoint verifies: every dataset-grounded Object Type has a complete binding, every dataset is ready with at least one row, and a smoke query succeeds for each binding. Only then does the stage advance. Ordinary queries never change project state.

Key engineering decisions:
- **Model/storage decoupling**: The contract (OntologyModelPackage) defines WHAT the business objects are. The binding (OntologyDatasetBinding) defines WHERE the data comes from. The query service is the only path that connects them. This means the same contract could later bind to a database, API, or streaming source without changing the contract itself.
- **Unified read boundary**: REST, future UI, Agent tools, and future MCP all go through the same `/runtime/query` service. No path reads files directly. No path bypasses the binding layer. This is the same pattern that makes the existing Agent tool registry safe — tools call services, not tables.
- **Provenance over power**: Every query response includes an `explain` block with package id/version/content_hash, binding id, dataset id/content_hash. This means any result can be traced back to the exact contract version and dataset file that produced it. Explain never includes filter values, raw rows, or file paths — it's a provenance record, not a data dump.
- **Deterministic type conversion with explicit errors**: If a column is declared as `integer` in the contract but a cell contains "not_a_number", the query returns type_errors with the field name, raw value, and error message. It never silently coerces or skips bad data. This is the same philosophy as the Phase 14.4 model validation gate: FAIL is a feature, not a bug.
- **No MCP, no DSL, no Graph RAG**: I deliberately did not implement a custom query language, an AST/optimizer, or an MCP runtime. The query contract is intentionally simple — equality filters only, no joins, no aggregations. This keeps the runtime explainable and auditable. MCP will be a future adapter over this same service, not a separate runtime.

Test coverage: 56 tests cover binding generation, idempotency, PK/property mapping, permissions (member/owner/admin/outsider), cross-group/cross-project isolation, field whitelisting, equality filtering, limit/offset, CSV and XLSX queries, contract type conversion (success and failure), explain/provenance sanitization, pilot activation (success, failure blocking, idempotency), path traversal rejection, and legacy backward compatibility. All 160 existing Phase 14 tests pass with zero regressions.

The interview narrative: "I didn't build a general data platform. I proved that a human-reviewed, evidence-grounded Ontology contract can deterministically bind to real datasets and serve explainable, permission-isolated queries — without SQL, without a custom query language, and without giving the model direct file access. The binding layer decouples WHAT from WHERE. The query service is the single read boundary for REST, Agent, and future MCP. Every result carries full provenance. And the activation gate ensures nothing goes to pilot without passing a smoke check."

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
