# Phase 11 Planning — Ontology Modeling Drafts v1

**Date**: 2026-06-19
**Status**: In progress — 11.1+11.2 delivered. Next: 11.3 deterministic draft generation.

---

## Phase 11 Goal

Turn the governed entity/relation/issue read model from Phase 9/10 into a human-reviewable modeling draft pipeline. Users can propose, review, and iterate on Object Type, Property, Link Type, and Action Type drafts — derived from existing ontology entities, frontmatter metadata, relations, citations, and governance issues — without Graph RAG, a full modeling studio, or Agent auto-write.

---

## Why Now

- Phase 9/10 delivered a reliable group-scoped entity/relation/issue read model with triage, curation backlog, graph console, and RAG evidence bridge.
- The existing ontology data (74 entities, 186 relations, 97 governance issues, 39 backlog entries) contains enough signal to seed modeling drafts.
- The next logical step toward the Ontology semantic operating layer is making the governed entities inform a structured model — but without introducing a full modeling studio, graph database, or autonomous Agent writes.
- This is the bridge from "governed knowledge" to "reviewable model" — the foundation for business objects, properties, relationships, and actions.

---

## Non-Goals

- Full Ontology modeling studio with CRUD for Object Types / Properties / Link Types / Action Types
- Graph RAG
- Graph database (Neo4j, etc.)
- Agent auto-creating, modifying, or publishing Ontology models
- Auto-modifying `F:\ontology-kb\knowledge-graph`
- Auto-fixing eval gold doc IDs
- Drafts becoming production schema without explicit human review and confirmation
- Web search integration with modeling drafts

---

## Proposed Task Slices

| # | Task | Description |
|---|------|-------------|
| 11.1 | Modeling draft boundary + schema design | ✅ Delivered (2026-06-19). `OntologyModelingDraft` model in `ontology_modeling_drafts` table, migration `0016_v16_ontology_modeling_drafts`. Fields: id, group_id, draft_type (object_type/property/link_type/action_type), name, description, status (proposed/accepted/rejected), source_entity_id, source_relation_id, source_issue_id, source_rag_run_id, evidence_refs, payload, created_by, created_at, updated_at, reviewed_by, reviewed_at, review_note. No unique constraint on (group_id, draft_type, name). |
| 11.2 | Draft read model / API | ✅ Delivered (2026-06-19). `POST /groups/{gid}/ontology/drafts` (owner/admin create proposed draft, validates source ids in group), `GET /groups/{gid}/ontology/drafts` (member+ read, filters: draft_type, status, source_entity_id, q). 16 tests covering create, read, permissions, isolation, evidence linkage ×4, draft_type/status/q filters, invalid draft_type 422, no-evidence rejection. |
| 11.3 | Draft generation from existing entities | Deterministic rules: entity_type → Object Type candidate, existing wikilinks → Link Type candidates, frontmatter fields → Property candidates. Backlog action_types (`create_missing_*`, `update_eval_gold_doc_id`) → human-action suggestions. No LLM, no Agent. |
| 11.4 | Human review workflow | Draft status: proposed → accepted / rejected. Review metadata: reviewer, reviewed_at, review_note. Bulk accept/reject for curated batches. |
| 11.5 | UI: entity detail modeling panel + draft list | Panel on entity detail (ontology.js): "Modeling Drafts" section showing proposed object/property/link drafts for this entity. Separate draft list view with status filter, source-entity links, review controls. Still not a full studio — focused, read-review-accept/reject workflow. |
| 11.6 | Agent-facing boundary review | Document what Agent may propose (read existing drafts, suggest new drafts via confirmation) vs. what Agent may NOT do (auto-create, auto-accept, auto-publish). Preserve HITL, audit, and permission checks. |

---

## First Implementation Slice Recommendation

**11.1 + 11.2**: Draft data model, migration, and read-only API. This establishes the foundation before generation or review workflows. Deliverables:

- Migration: `ontology_modeling_drafts` (objects/properties/links/actions with status, evidence, group_id)
- REST API: `GET /ontology/drafts/*` (member+), `POST /ontology/drafts/objects` (owner/admin)
- Pydantic schemas, group-scoped queries
- 10+ pytest tests covering create, read, status filter, group isolation, permissions

---

## Verification Strategy

- **Tests**: ≥10 new modeling draft tests per slice (CRUD, status lifecycle, group isolation, permissions, evidence linkage)
- **ruff**: clean across all changed files
- **pytest**: full suite pass at phase boundaries
- **verify_ui**: add smoke checks for draft panel and draft list
- **git diff --check**: clean on every commit

---

## Risks And Guardrails

| Risk | Guardrail |
|------|-----------|
| Draft generation produces noise (too many low-quality proposals) | Start with deterministic rules from existing entities; do not use LLM generation in v1 |
| Agent is given write access to modeling drafts | Phase 11.6 explicitly defines Agent boundary — Agent may read and propose, never auto-create/accept/publish |
| Modeling drafts drift into a full studio UX | Keep UI focused: entity detail panel + draft list only. No canvas editor, no drag-and-drop schema builder, no visual modeling tools |
| Drafts are confused with production ontology | Clear status lifecycle: proposed ≠ accepted ≠ production. No downstream pipeline consumes drafts |
| External KB modification temptation | Drafts live in app DB only. Never write back to F:\ontology-kb\knowledge-graph |

---

## Phase 11 Out of Scope

- Full Ontology modeling studio (visual editor, drag-and-drop, property panels)
- Graph RAG
- Graph database migration
- Agent auto-creating, modifying, or publishing Ontology drafts
- Auto-fixing eval gold doc IDs
- Auto-creating missing KB documents from backlog
- Web search integration with modeling
- Draft-to-production promotion pipeline
- Draft versioning / diff / merge
