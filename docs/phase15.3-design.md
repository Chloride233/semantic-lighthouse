# Phase 15.3 — Evidence-Backed Modeling Draft Candidate Design

**Status**: DESIGN DELIVERED. Implementation not started.

## Decision

Phase 15.3 closes the evidence-to-ontology feedback loop: reviewed project evidence (from 15.1 save + 15.2 display) feeds into modeling draft proposals, so ontology work is grounded in auditable, user-confirmed evidence — not LLM-only generation, not auto-accept, and not unwitnessed claims.

This design traces the path:

```text
ProjectEvidenceLink (reviewed, active)
  → candidate proposal (owner/admin, user-confirmed)
  → OntologyModelingDraft (proposed, source_rag_run_id + project_id + evidence_refs)
  → human review (accept/reject via existing 11.4 review flow)
  → existing package build (Phase 12.3 / 14.4)
```

No new models, migrations, or dependency for the minimal path. The existing `OntologyModelingDraft` schema already has all required fields.

## Why This Is Design-First

The existing `create_draft` endpoint (`POST /groups/{gid}/ontology/drafts`) already accepts `source_rag_run_id`, `project_id`, and `evidence_refs`. A user COULD craft these manually. The gap is product-level: no user-facing path connects "I see reviewed project evidence" to "I want to propose a draft grounded in that evidence."

This design answers:

- **What** does an evidence-backed candidate proposal look like?
- **How** does evidence map to draft fields?
- **What** goes in `evidence_refs`?
- **What** must NOT happen (LLM, auto-accept, external writes, etc.)?
- **What** implementation slices are needed, in what order?

## Schema Alignment

### Existing `OntologyModelingDraft` — already supports evidence-backed proposals

| Field | Existing? | Role in Evidence-Backed Draft |
|-------|-----------|-------------------------------|
| `source_rag_run_id` | ✅ FK → rag_runs.id | The RAG run whose answer was saved as project evidence |
| `project_id` | ✅ FK → business_projects.id | The Pilot project that owns the evidence |
| `evidence_refs` | ✅ JSON list | Bounded snapshot of evidence link metadata — provenance, not content |
| `draft_type` | ✅ enum | User selects or derives from evidence role |
| `name` | ✅ string | User-provided title |
| `description` | ✅ text | User-provided rationale, citing the evidence |
| `status` | ✅ "proposed" only | Always proposed — never auto-accepted |
| `payload` | ✅ JSON dict | Generator metadata (`generator: "evidence_backed_v1"`, candidate metadata) |
| `source_entity_id` | ✅ FK → ontology_entities | Optional — when evidence references a known entity |
| `source_issue_id` | ✅ FK → ontology_validation_issues | Optional — when evidence surfaces a governance issue |

### Existing validation in `create_draft` — already safe

- `source_rag_run_id` must belong to the same group (group isolation)
- `project_id` must belong to the same group (cross-group 404)
- At least one source pointer required (`evidence_refs` alone is NOT sufficient)
- Owner/admin only

**No schema change needed for the minimal path.**

## Candidate Proposal Shape

A candidate proposal is a user-initiated action: "take this piece of evidence and propose a modeling draft from it."

### Minimum fields (user provides)

| Field | Source |
|-------|--------|
| `draft_type` | User selects: object_type, property, link_type, or action_type |
| `name` | User enters a business-meaningful name |
| `description` | User explains the rationale — how the evidence supports this draft |

### Auto-populated fields (derived from evidence)

| Field | Source |
|-------|--------|
| `source_rag_run_id` | From the `ProjectEvidenceLink.evidence_id` (when evidence_type=rag_run) |
| `project_id` | From the `ProjectEvidenceLink.project_id` |
| `evidence_refs` | Bounded snapshot (see below) |

### `evidence_refs` shape (per evidence item)

```json
{
  "evidence_link_id": "uuid",
  "evidence_type": "rag_run",
  "evidence_id": "rag_run uuid",
  "role": "decision",
  "linked_at": "2026-06-21T12:00:00Z",
  "provenance_snapshot": {
    "question": "What are the key entities in the manufacturing workflow?",
    "confidence": "high",
    "retrieval_method": "hybrid",
    "citation_count": 4,
    "generated_at": "2026-06-21T11:55:00Z"
  }
}
```

Rules for `evidence_refs`:
- Each entry is a bounded JSON object with at most one nested `provenance_snapshot`; no paths or secrets
- `provenance_snapshot` uses the same bounded metadata that Phase 15.2 already exposes
- Never includes: raw prompts, raw answers, file paths, storage paths, secrets, tokens, stack traces
- At most 20 evidence items per draft (cap reused from `MAX_EVIDENCE_SAMPLES = 20`)

### Multiple evidence items

A single draft can reference multiple evidence links. This supports:
- A RAG run answer + a related document that corroborates it
- Multiple RAG runs that independently identified the same concept
- An evidence chain: context → decision → validation

All referenced evidence must belong to the same project and group (validated server-side).

## User Flow

### Step 1 — Evidence review surface (Phase 15.2 delivers this)

Owner/admin views the project evidence summary. Each evidence item shows type, role, saved time, and safe provenance. The surface already distinguishes document evidence from saved RAG answers.

### Step 2 — Propose draft from evidence (Phase 15.3 implements this)

Owner/admin selects one or more evidence items and clicks "Propose Draft Candidate." A form pre-populates with:

- Draft type selector (object_type / property / link_type / action_type)
- Name field
- Description field (template hint: "Based on the evidence question: ...")
- The evidence refs (read-only, selected items)

User fills in name, description, selects draft type, and submits.

### Step 3 — Server creates proposed draft

Existing `create_draft` flow with:
- All standard validations (group isolation, project_id check, source pointer required)
- Additional: validate that each evidence link ID in `evidence_refs.evidence_link_id` exists, is active, belongs to this project, and belongs to this group
- Status always "proposed"
- `payload.generator = "evidence_backed_v1"`
- `payload.evidence_link_ids = [...]` (audit trail)

### Step 4 — Existing review flow

The draft appears in the existing draft list. Owner/admin reviews/accepts/rejects via existing Phase 11.4 endpoints. No new review behavior.

### Step 5 — Existing package build

Accepted evidence-backed drafts join the pool for package building (Phase 12.3 / 14.4). The `source_draft_ids` in the package provide full audibility back to evidence.

## Implementation Slices

### Slice A: Evidence-backed candidate proposal endpoint (Standard Lane)

New endpoint: `POST /groups/{gid}/projects/{pid}/evidence-draft`

Request body:
```json
{
  "draft_type": "object_type",
  "name": "Manufacturing Work Order",
  "description": "Identified in the evidence question about manufacturing workflow entities...",
  "evidence_link_ids": ["link-uuid-1", "link-uuid-2"],
  "source_entity_id": null,
  "source_issue_id": null
}
```

Server:
1. Validates draft_type, name, description (standard)
2. Validates each evidence_link_id: exists, active, belongs to this project/group
3. Builds `evidence_refs` from the evidence links (provenance snapshots)
4. Determines `source_rag_run_id` from the first rag_run-typed evidence
5. Creates `OntologyModelingDraft` with all derived fields
6. Sets `payload.generator = "evidence_backed_v1"`
7. Returns the draft response (existing schema)

Idempotency: `generation_key` includes project_id, evidence_link_ids (sorted), draft_type, and normalized name. Re-submitting the same evidence set with the same type+name returns the existing proposed draft (200 instead of 201).

**This is the minimal implementation.** It reuses the existing `create_draft` logic internally, adding only the evidence-link validation bridge.

### Slice B: Frontend — evidence-to-draft proposal UI (Standard Lane)

In the Pilot workspace evidence panel:
1. Add checkbox selection on evidence items (owner/admin only)
2. Add "Propose Draft" button (enabled when ≥1 item selected)
3. Draft proposal form: type selector, name, description, evidence summary (read-only)
4. Submit → calls Slice A endpoint
5. Redirect to draft review or show success with draft ID

### Slice C: Evidence-only draft list filter (Standard Lane, optional)

Extend `GET /groups/{gid}/ontology/drafts` with `source` filter: `evidence_backed` to show only evidence-backed drafts. Reuses the `payload.generator` field for filtering.

## Boundaries (Hard)

**Must NOT:**
- LLM-only draft generation — all drafts are user-authored with evidence grounding
- Auto-accept — status always starts as "proposed"
- Auto-publish — no external KB writes, no production ontology modification
- Agent auto-writing Ontology — agent may read but never create/accept/publish
- MCP runtime, SDK, server, client, resources, or tools — MCP moratorium unchanged
- Graph RAG — no new retrieval path; reuse existing evidence links
- External KB writes — ontology modeling drafts are app-internal
- Full modeling studio — this is a targeted evidence→draft bridge, not a general-purpose modeling IDE
- New dependencies, hooks, or automation
- Hiding standalone draft/evidence pages

**Must maintain:**
- Group isolation on all queries
- Project isolation on evidence links
- Owner/admin restriction for writes
- Member read access for existing drafts (unchanged)
- All existing evidence link lifecycle rules (active/removed, status validation)

## Relationship to Existing Draft Generation

| Path | Source | Generator | Use Case |
|------|--------|-----------|----------|
| `POST /groups/{gid}/ontology/drafts` | Manual user entry | None (manual) | Ad-hoc proposals |
| `POST /groups/{gid}/ontology/drafts/generate` | Ontology scan data | `ontology_scan_v1` | Deterministic entity/relation drafts |
| `POST /projects/{pid}/model-drafts/generate` | Dataset assets | `dataset_deterministic_v1` | Phase 14.3 data-to-model |
| **`POST /projects/{pid}/evidence-draft`** | Project evidence links | `evidence_backed_v1` | **Phase 15.3 — this design** |

These are complementary, not competitive. Evidence-backed proposals handle the case where a human reviewed a RAG answer and decided it contains useful ontology insight — a path that scan-based generation cannot cover because it only sees structured entity data, not the content of RAG answers.

## Verification

Design-only — no code changes:
- `scripts/check_doc_alignment.py` — confirms no stale references
- `git diff --check` — confirms whitespace clean
- `git status --short` — confirms only doc files changed

Implementation verification (future Standard Lane):
- New endpoint tested for owner/admin/member/outsider/cross-group
- Evidence link validation: active/removed/gone/mismatched-project
- Idempotency: duplicate submission returns 200
- Evidence refs privacy: no raw prompts, no paths, no secrets
- Existing draft endpoints unchanged (regression)
- `ruff check` on changed files
