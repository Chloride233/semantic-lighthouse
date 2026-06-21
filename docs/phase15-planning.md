# Phase 15 Planning — Evidence-to-Ontology Feedback Loop v1

Status: 15.1 reviewed. 15.2 delivered. 15.3 DESIGN DELIVERED — see docs/phase15.3-design.md.

## Decision

Phase 15 starts with the gap left intentionally by S2.4C and exposed by S2.5A:

```text
project-scoped RAG answer
-> user confirms it is worth keeping
-> ProjectEvidenceLink records it as durable project evidence
-> later ontology/modeling work can use the reviewed evidence
```

This phase is not MCP runtime, not Graph RAG, not a full ontology modeling studio, and not Agent auto-writing Ontology.

## Why This Is Next

S2.4C made project-scoped RAG runs persist `RagRun.project_id` but deliberately did **not** auto-create `ProjectEvidenceLink`.

That distinction is correct:

- `RagRun.project_id` proves where an answer was generated.
- `ProjectEvidenceLink` proves a human intentionally attached that answer as project evidence.

S2.5A now lets users ask scoped questions inside Pilot. The next product step is a user-confirmed bridge from useful scoped answers into durable project evidence.

## Boundaries

Allowed:

- user-confirmed save of a project-scoped RAG run as project evidence
- reuse of existing `POST /groups/{gid}/projects/{pid}/evidence-links`
- clear UI state for already-linked answers, saved answers, and save failures
- later use of saved evidence as input to modeling draft proposals

Not allowed:

- automatic evidence linking
- Agent-created evidence links
- Agent accepting, publishing, or modifying Ontology
- MCP runtime, SDK, server, or client
- Graph RAG
- external KB writes or repairs
- full modeling studio
- hiding standalone pages

## Slices

### 15.1 — Save Scoped RAG Answer As Project Evidence

Lane: Standard. Delivered.

Goal: In the Pilot scoped Ask panel, let owner/admin intentionally save the generated project RAG answer as durable project evidence.

Implemented shape:

- Use the existing project-scoped RAG answer result from S2.5A.
- Add a secondary action: "保存为项目证据".
- Call existing `POST /groups/{gid}/projects/{pid}/evidence-links` with:
  - `evidence_type = "rag_run"`
  - `evidence_id = run_id`
  - `role = "decision"`
  - bounded note
- Show saved/already-linked state.
- Do not auto-create links after answer generation.

Owner/admin only. Members can ask but do not see the write action.

Verification:

- related frontend smoke via `scripts/verify_ui.py`
- `node --check` on changed JS files
- `git diff --check`

### 15.2 — Project Evidence Review Surface

Lane: Standard. Delivered.

Goal: Make saved RAG answers visible in the Pilot evidence summary, distinct from document evidence.

Expected implementation shape:

- Reuse `GET /groups/{gid}/projects/{pid}/summary` and/or evidence-link list.
- Show evidence type, role, saved time, and unavailable state.
- Do not show raw prompts, raw answer text, file paths, storage paths, secrets, or stack traces.

Delivered shape:

- Reuses `GET /groups/{gid}/projects/{pid}/summary`.
- Goal-stage project evidence summary distinguishes document evidence from saved RAG answers.
- Shows evidence type, role, saved time, safe provenance metadata, and unavailable state.
- Keeps raw prompts, raw answer text, file paths, storage paths, secrets, and stack traces out of the UI.

### 15.3 — Evidence-Backed Modeling Draft Candidate Design

Lane: Fast (design) → Standard (Slice A + B). DESIGN + SLICE A + SLICE B DELIVERED 2026-06-21. See `docs/phase15.3-design.md`.

Goal: Decide whether and how reviewed project evidence can feed modeling draft proposals.

Decision: Existing schema supports it. Implementation requires a new evidence→draft candidate endpoint (`POST /groups/{gid}/projects/{pid}/evidence-draft`) that bridges `ProjectEvidenceLink` to `OntologyModelingDraft` with user-authored name/description/type, auto-derived `source_rag_run_id`/`project_id`/`evidence_refs`, and `payload.generator = "evidence_backed_v1"`. No new models or migrations needed. Three implementation slices (A: endpoint, B: frontend, C: filter) defined in the design doc.

Rules enforced:

- no LLM-only draft generation — user authors name, description, draft_type
- no auto-accept — status always proposed
- no publish — no external KB writes
- no external KB write
- generated proposals carry `source_rag_run_id`, `project_id`, and bounded `evidence_refs`
- evidence link validation: must exist, be active, belong to the same project/group

Slice A delivered shape:

- New endpoint: `POST /groups/{gid}/projects/{pid}/evidence-draft` (in `ontology.py` as `evidence_draft_router`).
- Request: `EvidenceDraftCreateRequest` — draft_type, name, description, evidence_link_ids (non-empty, max 20), optional source_entity_id/source_issue_id.
- Server derives source_rag_run_id (first rag_run-typed link), evidence_refs (bounded provenance snapshot per link), payload.generator="evidence_backed_v1", payload.evidence_link_ids.
- Idempotency: same group, project, sorted link IDs, draft_type, normalized name → 200 with existing proposed draft.
- Bounded provenance in evidence_refs: never includes raw prompt, raw answer, raw_content, source_path, storage_path, secrets, tokens, or stack traces.
- 22 tests: permissions (owner/admin/member/outsider), isolation (cross-group project/link, cross-project link), validation (removed link, empty links, invalid type, nonexistent link), source_rag_run_id derivation (rag_run, document-only, mixed), idempotency (duplicate, different name, different links), evidence_refs privacy (no raw answer, no raw_content/path, no secrets), draft lifecycle (visible in list, status always proposed).
- Zero regressions: 35 existing evidence tests + 29 existing ontology draft tests pass unchanged.

Slice B delivered shape:

- In Pilot goal stage, owner/admin see checkboxes on each evidence item (disabled for unavailable/gone evidence).
- "提出建模草案" button appears in a toolbar below the evidence list, enabled when ≥1 evidence item is selected.
- Clicking opens a dialog with: draft_type select (object_type/property/link_type/action_type), name input, description textarea, selected evidence read-only summary.
- Submit calls `POST /groups/{gid}/projects/{pid}/evidence-draft` (Slice A endpoint).
- Success: toast with draft name, evidence selection cleared, summary refreshed.
- Failure: human-readable error in dialog, form remains for correction.
- Controls hidden for members and archived projects.
- No raw prompts, answers, paths, secrets, tokens, or stack traces exposed in UI.
- 53/53 UI regression tests pass (`scripts/verify_ui.py`).
