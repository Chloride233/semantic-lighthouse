# Phase 11 Planning — Ontology Modeling Drafts v1

**Date**: 2026-06-19
**Status**: Phase 11 backend complete (11.1–11.4+11.6 delivered). UI (11.5) deferred to Kimi frontend refactor. Next → Phase 12 planning.

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
| 11.1r | **Review hardening: rescan evidence lifecycle** | ✅ Review hardened (2026-06-19). `scan_group()` preserves draft evidence pointers across rescans: nulls FK → deletes old entities/relations/issues → rebuilds → relinks via stable keys (entity: `document_id`, relation: `(source_document_id, target_path, target_label, relation_type)`, issue: `issue_key`). Intermediate flushes added for strict FK safety. evidence_refs tightened: must have real `source_*_id`, evidence_refs-only rejected. 10 new tests (entity/relation/issue relink, vanished evidence, metadata preservation, rag_run unaffected, cross-group isolation, evidence_refs-only rejection, FK enforcement regression). 26 draft + 41 ontology = 67 related tests passing. Full suite 307/311 (4 pre-existing E2E failures). |
| 11.2 | Draft read model / API | ✅ Delivered (2026-06-19). `POST /groups/{gid}/ontology/drafts` (owner/admin create proposed draft, validates source ids in group), `GET /groups/{gid}/ontology/drafts` (member+ read, filters: draft_type, status, source_entity_id, q). |
| 11.3 | Draft generation from existing entities | ✅ Deterministic rules: entity_type → Object Type candidate, existing wikilinks → Link Type candidates, frontmatter fields → Property candidates. Backlog action_types (`create_missing_*`, `update_eval_gold_doc_id`) → human-action suggestions. No LLM, no Agent. |
| 11.4 | Human review workflow | ✅ Delivered (2026-06-19). Single + batch review endpoints. Status transitions: proposed → accepted/rejected (one-way, final, 409 on re-review). Batch atomic (all-or-nothing). Rejected requires non-empty review_note (model_validator). Review never modifies payload, evidence_refs, created_by, created_at, or source pointers. 33 tests. No Agent access. |

| 11.5 | UI: entity detail modeling panel + draft list | **Deferred** — panel and draft list UI deferred to Kimi unified frontend refactor. CC iterations do no frontend work (no static/js, no CSS, no HTML, no verify_ui, no Playwright). |
| 11.6 | Agent-facing boundary review | ✅ Delivered (2026-06-19). `docs/ontology-agent-boundary.md` defines current runtime boundary (3 tools, no ontology draft tool), allowed behavior (evidence retrieval, non-persistent suggestions), disallowed behavior (no draft create/generate/review/publish Agent tool, no auto-persist, no HITL/audit bypass), and future gate (6 required conditions). Zero code changes. |

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

---

## Phase 11.3 Delivery Record (2026-06-19)

### Generation Rules

**Object Type drafts**: one per distinct `entity_type` in group. Name = entity_type value. Generation key: `object_type:<normalized_entity_type>`. Source = first entity sorted by (source_path, id). Evidence = up to 20 entity samples.

**Property drafts**: one per distinct (entity_type, frontmatter_field). Fields `entityType`/`documentType` excluded. Name = `<EntityType>.<field_name>`. Generation key: `property:<entity_type>:<field>`. Observed value types and counts recorded in payload. Empty/illegal field names skipped.

**Link Type drafts**: one per (source_entity_type, relation_type, target_entity_type) for resolved relations only (status=resolved, target_entity_id not null). Name = `<Src> -> <Tgt> (<rel_type>)`. Generation key: `link_type:<src>:<rel>:<tgt>`. Unresolved relations excluded.

**Action Type drafts**: one per action_type for confirmed issues only (triage_status=confirmed). Action type derived via `determine_action_type()` (moved from curation demo to service). Pending/ignored issues excluded. Name from human-readable mapping. Generation key: `action_type:<action_type>`. Payload scope: `ontology_governance`.

### API

- `POST /groups/{group_id}/ontology/drafts/generate` — owner/admin only. Member → 403. No entities → 400.
- Response: `DraftGenerationResponse` with `generated_count`, `existing_count`, `skipped_count`, `counts_by_type` (object_type, property, link_type, action_type).

### Idempotency Strategy

Two-layer dedup before inserting:
1. **Generation key**: stable key in `payload.generation_key` — must not exist in any existing draft's payload for the group.
2. **Type + normalized name**: `(draft_type, name.strip().casefold())` match prevents duplicates even if keys differ.

Never modifies existing drafts' status, payload, reviewed_by, reviewed_at, review_note.

### Files Changed

| File | Change |
|------|--------|
| `src/semantic_lighthouse/services/ontology_drafts.py` | **New**: `generate_modeling_drafts()`, `determine_action_type()` |
| `src/semantic_lighthouse/schemas.py` | +`DraftGenerationCountsByType`, +`DraftGenerationResponse` |
| `src/semantic_lighthouse/routers/ontology.py` | +`POST /drafts/generate` endpoint |
| `scripts/run_ontology_curation_demo.py` | Import `determine_action_type` from service (removed local def) |
| `tests/test_ontology_draft_generation.py` | **New**: 25 tests (permissions, all 4 draft types, idempotency, manual protection, evidence scoping, response schema) |

### Verification

- `pytest`: 332 passed, 4 failed (pre-existing E2E: test_console_e2e.py Playwright auth timing)
- 127 related tests pass (25 generation + 26 draft + 41 ontology + 35 curation demo)
- `ruff check src tests scripts`: All checks passed
- `git diff --check`: clean

### Boundaries Preserved

- No LLM, no Agent, no UI, no review/accept/reject
- `determine_action_type` moved to service; demo script and 35 curation tests unaffected
- No external KB modification
- Group-scoped queries; cross-group isolation verified
- No new migration
- No stale generated draft cleanup

## Phase 11.4 Delivery Record (2026-06-19)

### Human Review Workflow Design

**Single Review API**: `POST /groups/{group_id}/ontology/drafts/{draft_id}/review`
- Only `accepted` or `rejected` statuses accepted — no reopening, no overwriting.
- `rejected` requires non-empty `review_note`; `accepted`'s note is optional.
- `review_note` whitespace-trimmed before storage.

**Batch Review API**: `POST /groups/{group_id}/ontology/drafts/review-batch`
- 1–100 draft IDs. Duplicates deduplicated (counted once).
- All-or-nothing atomicity: any missing/cross-group ID → 404; any already-reviewed → 409. Zero partial updates.
- All drafts receive same reviewer, reviewed_at, and review_note.
- Response is compact: `reviewed_count`, `status`, `draft_ids`, `reviewed_by`, `reviewed_at`.

**Status Transition Rules (v1)**:
| From | To | Allowed? |
|------|-----|----------|
| proposed | accepted | ✅ |
| proposed | rejected | ✅ |
| accepted | anything | ❌ 409 |
| rejected | anything | ❌ 409 |

- First reviewer metadata (`reviewed_by`, `reviewed_at`, `review_note`) never overwritten — 409 preserves original audit trail.
- No `reopen`/`unreview` endpoint. Once decided, the decision is final.
- Draft payload, evidence_refs, created_by, created_at, and source pointers are never modified by review.

**Permissions**: `require_group_role(db, ..., {"owner", "admin"})` — member returns 403, outsider returns 403.
**Cross-group isolation**: Queries always include `group_id`; cross-group draft ID returns 404 (no existence leak).
**Route ordering**: Static `/drafts/review-batch` registered before dynamic `/drafts/{draft_id}/review` to prevent FastAPI path conflicts.

### Schema Additions

- `OntologyModelingDraftReviewRequest` — `status: ^(accepted|rejected)$`, `review_note: str|null max 2000`, `@model_validator(mode="after")` for rejected-note requirement.
- `OntologyModelingDraftBatchReviewRequest` — same validation + `draft_ids: list[str] min 1 max 100`.
- `OntologyModelingDraftBatchReviewResponse` — compact response: `reviewed_count`, `status`, `draft_ids`, `reviewed_by`, `reviewed_at`.

### Test Coverage (33 new tests)

| Class | Tests | Coverage |
|-------|-------|----------|
| TestSingleAcceptReject | 5 | owner accept, owner reject with note, rejected without note → 422, accepted without note OK, whitespace-only note → 422 |
| TestReviewPermissions | 5 | admin review, member 403 single, member 403 batch, outsider 403, cross-group 404 |
| TestInvalidInput | 3 | invalid status 422 (proposed + invalid), empty batch 422, >100 batch 422 |
| TestStatusTransitions | 3 | accepted → 409, rejected → 409, admin re-review of accepted → 409 preserves original metadata |
| TestReviewPreservesMetadata | 5 | payload, evidence_refs, created_by/created_at, source pointers unchanged, whitespace stripping |
| TestDraftStatusFilter | 2 | GET ?status=accepted, GET ?status=rejected |
| TestBatchReview | 7 | batch accept 2, batch reject 3 with note, duplicate dedup, missing ID → atomic 404, cross-group → atomic 404, already-reviewed → 409 no partial, all-reviewed → 409 |
| TestReviewAnyDraft | 3 | generated draft reviewable, manual draft reviewable, batch mixed |

### Verification

- `pytest`: 365 passed, 4 failed (pre-existing E2E Playwright auth timing — unchanged)
- Related tests: 125/125 (33 review + 26 draft + 25 generation + 41 ontology)
- `ruff check src tests`: All checks passed
- `git diff --check`: clean
- No new migration needed — all review fields already on the model from 11.1.

### Non-Goals Preserved

- No UI, no modeling studio, no draft content editing
- No publish / draft-to-production / production Ontology write
- No Graph RAG, no graph database
- No Agent review/write/auto-create
- No external KB modification
- No DELETE / PATCH / reopen endpoint
- No new migration
- No 11.5 UI (deferred to Kimi frontend refactor).

**Next**: Phase 12 planning — see `docs/project-roadmap.md`.
