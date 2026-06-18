# Phase 10 Planning — Governance Operations & Demo Polish

**Date**: 2026-06-18
**Status**: 10.1–10.2 delivered; 10.3–10.5 pending

---

## What Phase 9 Proved

- **Read-only ontology governance works**: 74 real KB documents → 74 entities, 186 relations, 97 issues surfaced without modifying external KB.
- **The KB has real drift**: 90 unresolved wikilinks (mostly `research/*` missing), 7 stale eval gold IDs.
- **The pipeline is deterministic**: scan → validate → extract entities → extract relations → surface issues → graph UI. All group-scoped, permission-aware.
- **Agent is a controlled coordination layer**: no Agent auto-write to Ontology at any point in Phase 8–9.

## What the KB Demo Exposed

- `research/` directory referenced by wikilinks does not exist in the KB.
- 7 eval gold document IDs not present in imported KB.
- 96 of 186 relations are resolved — substantial internal link density.
- No duplicate titles or aliases — entity identity quality is good.

## Phase 10 Goal

Make ontology governance operational — turn scan findings into triageable work items, polish the demo loop, and build the bridge from RAG evidence to ontology entities without Graph RAG, a modeling studio, or Agent auto-write.

## Phase 10 Tasks

| # | Task | Description |
|---|------|-------------|
| 10.1 | Governance issue triage design | ✅ `triage_status` field, `POST /ontology/issues/{id}/triage`, frontend triage controls. Triage states: pending / confirmed / ignored. Audit: triaged_by, triaged_at, triage_note. |
| 10.2 | Real KB curation demo script | ✅ `scripts/run_ontology_curation_demo.py` — deterministic triage of 97 issues → 39 backlog entries; rescan persistence verified; curation backlog is human action guidance only, does NOT auto-fix KB. |
| 10.3 | Ontology graph UX polish | Filterable graph, improved labels, edge hover/legend, mobile. Still read-only SVG. |
| 10.4 | Evidence-to-ontology bridge | RAG citations and tasks link to ontology entities (source document match). Read-only bridge. |
| 10.5 | Phase 10 review | Re-run governance demo, verify triage + graph + bridge end-to-end. |

## Phase 10 Out of Scope

- Graph RAG
- Full modeling studio (Object Type / Property / Link Type / Action Type editor)
- Agent auto-writing ontology entities, relations, or actions
- External KB auto-fix
- Graph database migration (Neo4j, etc.)
- Web search integration with ontology
- Phase 9 data model rewrites
