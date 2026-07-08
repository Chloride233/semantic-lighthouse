# Semantic Lighthouse Roadmap

Canonical status lives in [project-status.toml](project-status.toml). This roadmap is intentionally short: it records the current delivery baseline, the active product boundary, and the next decision candidates. Historical phase notes are archived in [archive/project-roadmap-history.md](archive/project-roadmap-history.md).

## Current Baseline

| Line | State |
|------|-------|
| Phase 1-18 | Complete: auth, group isolation, ingestion, retrieval, RAG, controlled Agent workflow, ontology governance, modeling drafts, packages, business contracts, pilot workflow, deployment smoke, frontend baseline |
| Phase 19 | Complete: offline ontology operationalization from CSV data pack to manifest, mapping contract, deterministic business rules, and governance feedback |
| R2 | Complete: relationship runtime traversal foundation with group-scoped API and audit |
| R3A-R3F | Complete: grouped output, filter pushdown, bidirectional traversal, stable sorting, and FK indexing |

The product should still be read as an ontology-oriented semantic operating layer. RAG and Agent features are support systems, not the product center.

## Active Boundary

- Keep `group_id` server-derived and enforced across documents, chunks, retrieval, RAG, conversations, tasks, Agent runs, ontology objects, projects, datasets, bindings, outcomes, and evidence links.
- Keep write-like Agent behavior behind backend authorization, audit/provenance, and user confirmation.
- Keep MCP runtime out of scope until a dedicated Safety Lane phase approves identity, authorization, audit, provenance, SDK/dependency, and HITL boundaries.
- Keep runtime traversal bounded. Aggregation, SQL-like DSLs, Graph RAG, and autonomous writes remain deferred unless a real pilot demand justifies the risk.
- Treat Phase 19 governance feedback as offline artifact scope until DB-backed governance issue delivery is explicitly chosen.

## Decision Gate

The project is past broad foundation building. The next phase should be selected by proof value, not by feature count:

1. Does it make the semantic operating layer more inspectable, governed, or reusable?
2. Does it convert evidence into controlled business action rather than generic chat?
3. Can it be verified with deterministic tests or bounded smoke scripts?
4. Does it avoid widening into an Agent platform, analytics DSL, or infrastructure showcase?

## Next Step Candidates

| Candidate | Why It Matters | Lane |
|-----------|----------------|------|
| Semantic CI/CD productization | Turns ontology mapping, rules, evidence, and governance feedback into a repeatable delivery discipline | Standard |
| HITL evidence packet | Makes user confirmation stronger by showing source evidence, proposed action, affected objects, risk, and rollback notes before writes | Standard/Safety |
| Strong/weak relation governance | Separates contractual relations from inferred/weak relations so the ontology graph stays useful without pretending all edges are equal | Standard |
| AdventureWorks benchmark | Adds a recognizable external benchmark for sales/order/customer scenarios and cross-project credibility | Standard |
| Metric-to-ontology mapping MVP | Connects business KPIs to ontology objects, properties, evidence, and lineage without opening a broad analytics DSL | Standard/Safety |

## Near-Term Slimming Rules

- Prefer short active docs plus archived historical records.
- Keep demo scripts only when they verify a named project capability or document a still-relevant historical slice.
- Keep legacy console routes working unless an explicit retirement task covers UX, redirects, tests, and docs.
- Do not remove migrations, tests, audit paths, or permission checks as cleanup.

## Deferred

| Item | Reason |
|------|--------|
| R3E2 aggregation | Crosses from traversal into analytics query semantics |
| Runtime MCP | Needs a separate Safety Lane decision |
| Graph RAG | Wait until ontology read models and relation semantics are reliable enough |
| DB-backed governance feedback | Valuable, but it changes persistence and review workflow |
| Production enterprise deployment hardening | Requires real environment assumptions that this showcase repo does not include |
