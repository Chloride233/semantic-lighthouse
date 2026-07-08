# Agent Handoff

Canonical project status lives in [project-status.toml](project-status.toml). Use that file for the current phase, verification counts, MCP status, frontend status, and next decision gate.

## Current Working Frame

- Product boundary: ontology-oriented semantic operating layer for enterprise AI transformation.
- Delivery chain: auth/group isolation -> ingestion -> retrieval evidence -> citation-grounded RAG -> user-confirmed task/action -> controlled Agent workflow -> ontology governance/modeling/package -> dataset binding -> runtime query/traversal -> outcome artifact -> governance feedback.
- Current decision posture: no automatic phase expansion. Choose the next slice by proof value and boundary discipline.

## Handoff Notes

- Keep runtime MCP as design-only until a dedicated Safety Lane phase approves scope and boundaries.
- Keep legacy console routes working unless a retirement task explicitly covers redirects, tests, and docs.
- Treat Phase 19 governance feedback as offline artifacts until DB-backed issue workflow is selected.
- Do not remove migrations, tests, permission checks, audit paths, or evidence/provenance surfaces as cleanup.

## Suggested Next Slices

See [project-roadmap.md](project-roadmap.md) for the active candidates: Semantic CI/CD productization, HITL evidence packet, strong/weak relation governance, AdventureWorks benchmark, and metric-to-ontology mapping MVP.
