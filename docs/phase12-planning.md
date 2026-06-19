# Phase 12 Planning — Ontology Model Quality & Contract Packages v1

**Date**: 2026-06-19
**Status**: 12.1 real KB demo delivered. Technical integrity PASS. Next → 12.2 draft quality gates.

---

## Phase 12 Goal

Turn Phase 11 accepted modeling drafts into verified, quality-gated, immutable
model contract packages — without treating accepted drafts as production schema,
without Graph RAG, and without Agent auto-write.

---

## Why Now

- Phase 11 backend delivered a working draft pipeline: deterministic generation
  (11.3), human review (11.4), and explicit Agent boundary (11.6).
- Accepted drafts exist as audited human decisions, but their quality has not
  been measured against the real ontology KB.
- Before building a production promotion path, we need to verify that Phase 11
  generation produces useful candidates at acceptable noise levels.
- The downstream path from accepted draft to production schema should be a
  deliberate, versioned, immutable contract — not a live mutation of the draft.

---

## Core Judgment

**Accepted drafts are NOT production schema.** They are human-confirmed
proposals. Before they inform production systems, they must:

1. Be measured against real KB generation output for quality and noise.
2. Pass explicit draft-level quality gates (generation_key, source pointer,
   evidence, payload structure, cross-reference consistency).
3. Be assembled into an immutable, versioned model contract package with a
   content hash and audit trail.
4. Remain app-internal (not published to external KB, not auto-ingested by
   downstream systems).

---

## Proposed Task Slices

| # | Task | Description |
|---|------|-------------|
| 12.1 | Real KB modeling draft demo | Run Phase 11 generation against real ontology KB (74 entities, 186 relations, 97 issues, 39 backlog entries). Collect counts by type. Identify over-generation, naming collisions, invalid properties, evidence gaps. Output quality report. No auto-accept/reject. No new migration. |
| 12.2 | Draft quality gates | Validate mandatory draft structure: generation_key presence, source pointer validity, evidence_refs shape, required payload fields per draft_type. Validate cross-reference consistency (object↔property, link↔source+target). Output validation issues — never auto-modify draft status. |
| 12.3 | Immutable model package read model | From accepted drafts, create a versioned snapshot (`ontology_model_packages`). Package records: group_id, version, content_hash, created_by, created_at, source draft IDs. Immutable after creation — no UPDATE path. |
| 12.4 | Package read/export API | Member-visible GET for packages. Owner/admin POST to create package from accepted drafts. Export stable JSON contract (not production publish). |
| 12.5 | Action and permission contract | For action_type drafts, declare required_role, confirmation_requirement, and evidence_requirement in the package contract. Declarative only — no execution. |
| 12.6 | Real demo and phase review | Verify accepted drafts → package → JSON contract repeatability and audit chain. End-to-end quality report. |

---

## First Implementation Slice Recommendation

**12.1 Real KB modeling draft demo.**

- Reuse the Phase 10 curation demo pattern: import real KB, scan, triage, then
  `POST /drafts/generate`.
- Collect counts by draft_type. Assess naming quality, evidence coverage,
  noise rate.
- Output: `docs/phase12-real-kb-draft-report.md` or equivalent.
- Gate: if generation produces predominantly noise (>50% drafts with
  insufficient evidence or meaningless names), pause 12.2/12.3 until
  generation rules are improved (base Phase 11 fix, not Phase 12 scope creep).
- Zero new migration. Zero API changes. Zero Agent involvement.

---

## Explicit Non-Goals

- Frontend, static/js, CSS, HTML, verify_ui, Playwright, E2E.
- Full Ontology modeling studio (visual editor, drag-and-drop, property panels).
- Graph RAG or graph database (Neo4j, etc.).
- Auto-accept or auto-reject drafts.
- Auto-publish model package to external systems.
- Agent creation, review, or publication of packages.
- Modification of `F:\ontology-kb\knowledge-graph`.
- Draft/package direct write to production business systems.
- Phase 11.5 UI (deferred to Kimi frontend refactor).

---

## Known Inputs

From Phase 9/10 real KB demos:
- 74 entities across 9 entity_types (Concept 44, Case 12, Vendor 8, Product 4,
  Methodology 3, FAQ 1, Person 1, Proposal 1).
- 186 relations (96 resolved, 90 unresolved).
- 97 issues (90 unresolved_wikilink, 7 stale_eval_gold_doc_id), all confirmed
  via curation demo → 39 backlog entries.
- Schema with 9 entityTypes, 5 controlled fields (entityType, tags, created,
  status, source), plus shared optional fields (aliases, updated, description).

Expected Phase 11.3 generation ballpark (not yet run):
- Object Type: ~9 (one per entity_type).
- Property: ~30–60 (entity_type × frontmatter fields, excluding entityType/documentType).
- Link Type: up to 96 (resolved relation type pairs, deduplicated).
- Action Type: up to 5 (distinct action_types from confirmed issues).

---

## Verification Strategy

- 12.1: script output diffable against expected counts; manual quality spot-check.
- 12.2: schema-level validators returning issue lists, not modifying drafts.
- 12.3: migration + model + create/read tests + immutability gate.
- 12.4: REST tests for permissions, isolation, export format stability.
- 12.5: schema validation for action_type required fields in package.
- 12.6: full-chain demo script with audit trail verification.

---

## Phase Transition Rules

Phase 12 slices gate on 12.1 results:
1. If generation quality passes threshold → proceed to 12.2+12.3.
2. If generation is noisy → fix generation in a Phase 11.x maintenance slice
   before building packages on top of low-quality drafts.
3. Packages remain app-internal throughout — no external publish without a
   separate future phase.

---

## Phase 12.1 Delivery Record (2026-06-19)

### Real KB Results

Ran `scripts/run_ontology_modeling_demo.py` against real KB (74 entities, 186 relations,
97 confirmed issues) via `scripts/run_ontology_curation_demo.py` group.

| Draft Type | Count |
|------------|-------|
| object_type | 8 |
| property | 48 |
| link_type | 17 |
| action_type | 3 |
| **Total** | **76** |

**Expected vs actual**: Object types 8/9 (Concept/Vendor/Product/Methodology/Case/FAQ/Person/Proposal — Research entity_type has no entities in current KB, so 8 is correct). Properties 48 (within expected 30–60). Link types 17 (far below 96 max — heavy dedup by type pair). Action types 3 (review_link_target, update_eval_gold_doc_id, create_missing_research_doc — missing_research_doc_or_directory and create_or_rename_entity_doc both map to review_link_target via determine_action_type, so 3 distinct is correct).

### Quality Checks

| Check | Result |
|-------|--------|
| Missing generation_key | 0 |
| Missing source pointer | 0 |
| Empty evidence_refs | 0 |
| Duplicate (type, name) | 0 |
| Second generation idempotent | YES |

### Noise Indicators

- 19/48 properties backed by a single entity (weaker signal — entity-count=1)
- 5/17 link types backed by a single relation (weaker signal)
- 0/3 action types backed by a single issue
- Proposal entity type yields 10 properties from only 1 entity — high noise risk

### Decision

**Technical integrity: PASS**. All hard checks are zero, generation is idempotent,
all drafts carry evidence. The deterministic generation pipeline produces
structurally valid candidates.

**Recommendation**: Proceed to Phase 12.2 (draft quality gates). Noise indicators
are informational — they flag candidates with weaker evidence for human scrutiny,
not failures. Quality gates should validate per-draft structure and cross-reference
consistency before any draft is accepted for package assembly.

**Report**: `docs/ontology-modeling-draft-demo-report.md`
