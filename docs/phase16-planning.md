# Phase 16 Planning — Pilot Outcome & FDE Delivery Record v1

Status: 16.1–16.2 DELIVERED — slices 16.3–16.4 pending.

## Decision

Phase 16 turns the completed Pilot workflow chain (goal → data → model → validate → pilot)
into a durable, auditable **delivery record** suitable for FDE handoff, interview
demonstration, and portfolio evidence.

```text
business goal
→ datasets (profiled, with PK/FK suggestions)
→ project evidence (RAG answers + document citations, user-confirmed)
→ modeling drafts/packages (evidence-backed, reviewed, quality-gated)
→ pilot runtime query findings (binding + typed filter + CSV output)
→ decision/outcome narrative + risks + next actions
→ durable delivery record
```

This is NOT a reporting engine, NOT a full PM system, NOT a PDF generator,
and NOT a marketing page.

## Why This Is Next

### What problem it solves for a new enterprise/FDE user

A new enterprise user or FDE reviewer opens Semantic Lighthouse and asks:
"What did this pilot actually deliver?"

Without Phase 16, the answer is scattered across:
- Project summary endpoint (partial)
- Evidence list (raw links)
- Draft list (modeling artifacts)
- Package list (quality-gated snapshots)
- Runtime query results (CSV output)
- No single durable record ties them together.

Phase 16 produces one deliverable: **the outcome record**. It proves the pilot
was not just feature exploration — it produced a traceable chain from business
goal to evidence to model to runtime findings to a decision.

### How it fits the Ontology semantic operating layer north star

The north star path is:

```text
fragmented knowledge → trusted evidence → governed entities/relationships
→ business objects, actions, permissions, Agent interfaces
→ enterprise Ontology semantic operating layer
```

An outcome record is the **proof artifact** that the chain worked for a specific
business domain. Without it, the system has all the pieces but no closing argument.
With it, every pilot produces a governed, auditable record that:

- **Names the business goal** the Ontology was built to serve.
- **Cites which evidence** grounded the modeling decisions.
- **References which model packages** passed quality gates.
- **Records runtime query findings** that prove the contract reads real data.
- **Captures the decision** — what the enterprise should do next.

This is the "semantic" in semantic operating layer: meaning is not just in the
graph nodes, it's in the narrative that connects them to business outcomes.

### Why this is higher priority than alternatives

| Alternative | Why deferred |
|-------------|--------------|
| More filters / search tuning | Phase 15 closed the evidence→model loop. The system already retrieves and filters adequately for demo. |
| Graph RAG | Governance graph exists (Phase 9). Graph RAG is a retrieval technique, not a product outcome. Wait until the entity/relation read model has production data. |
| MCP runtime | Design exists (Phase 11.6). MCP is a future adapter candidate, not current product. Requires dedicated Safety Lane plan. |
| Modeling studio | Phase 11–13 delivered modeling drafts, packages, and contracts through deterministic rules + human review. A full studio is a UI project, not a product gap. |
| More Agent features | Agent is a controlled coordination layer. The pilot already demonstrates Agent audit + HITL. Adding Agent features does not close the delivery gap. |
| Object Runtime / Action execution | Phase 13–14 explicitly scoped these out. The runtime already reads. Writing requires production safety work. |

**Phase 16 closes the demo loop.** It answers "what did the pilot achieve?"
without requiring the reviewer to click through 6 pages and read raw API output.
This is the artifact a hiring manager or FDE reviewer actually wants to see.

## Scope

### In scope

- **16.1 Outcome record design**: Decide what fields belong in a delivery record,
  whether to reuse existing project/package/query audit data, and whether a
  durable table is required.
- **16.2 Read-only outcome summary endpoint**: Reuse existing `ProjectSummary`,
  packages, runtime audit/query outputs. Member+ read, owner/admin create/update
  only if write is needed.
- **16.3 Pilot delivery report UI**: In Pilot workspace, show an outcome panel
  with goal, evidence, model package, validation state, key query result
  summaries, risks, and next actions. This is a working FDE handoff view.
- **16.4 Exportable interview/demo artifact**: Generate or display a concise
  delivery record suitable for demo/interview. HTML/markdown first; no PDF
  dependency unless already available.

### Out of scope (hard boundaries)

- No Graph RAG.
- No MCP runtime.
- No Agent auto-write.
- No external KB write.
- No autonomous publish.
- No new framework/dependency.
- No broad frontend redesign.
- No full PM system.
- No full reporting engine.
- No PDF/export dependency unless already available.
- No raw dataset paths, raw prompts, raw answers, secrets, or stack traces in
  the outcome record.

## Suggested Slices

### 16.1 — Outcome Record Design / Schema Boundary ← DELIVERED 2026-06-21

**Lane: Safety (migration + model + API + tests).**

**Delivered shape**:

- New model: `PilotOutcomeRecord` in `models.py` (table `pilot_outcome_records`).
- Migration: `0027_v27_pilot_outcome_records` — adds table with `id`, `group_id`, `project_id`, `title`, `business_goal_snapshot`, `selected_evidence_refs` (JSON), `package_refs` (JSON), `query_refs` (JSON), `decision_summary`, `risks` (JSON), `next_actions` (JSON), `created_by`, `created_at`.
- Router: `routers/outcomes.py` — registered at `/groups/{gid}/projects/{pid}/outcomes`.
- API:
  - `POST /groups/{gid}/projects/{pid}/outcomes` — owner/admin create immutable record. Snapshots project's `business_goal`. Validates evidence links (active, same group/project), packages (same group, matching project if scoped), and query_refs (forbidden key rejection).
  - `GET /groups/{gid}/projects/{pid}/outcomes` — member+ list, latest first, limit 1–100 default 20.
  - `GET /groups/{gid}/projects/{pid}/outcomes/{outcome_id}` — member+ get single, 404 across group/project boundary.
- No PATCH/DELETE. Multiple records per project allowed.
- Evidence refs: bounded provenance via `_build_provenance` (no raw_content, answer, prompt, paths).
- Package refs: id/version/content_hash/quality_status/draft_count only (no contract_json, source_draft_ids).
- Query refs: validated recursively for forbidden keys (raw_content, answer, prompt, source_path, storage_path, secret, token, password, key, api_key, stack_trace, traceback, raw, csv_rows, raw_csv).
- Schemas: `PilotOutcomeCreateRequest` (with `_validate_query_refs_safe` recursive validator), `PilotOutcomeResponse`, `PilotOutcomeListResponse`.
- Tests: `tests/test_pilot_outcomes.py` — 40 tests:
  - Create: owner/admin OK, member/outsider reject, cross-group 404, title validation, snapshot, multiple records.
  - Evidence validation: valid accepted, nonexistent/other-project/removed/other-group rejected.
  - Package validation: valid accepted, nonexistent/other-group/other-project reject.
  - Query refs privacy: clean accepted, raw_answer/source_path/secret/stack_trace/nested/csv_rows rejected.
  - Read: owner/member OK, outsider 403, cross-group 404, nonexistent 404.
  - List: empty, latest-first, member OK, outsider 403, limit, per-project isolation.
  - Privacy: create/get/list responses contain no forbidden terms.
- **Design decisions resolved**:
  - New `PilotOutcomeRecord` table (not extending BusinessProject).
  - Immutable after creation (no PATCH/DELETE).
  - Snapshots business_goal at creation time; evidence/package refs built from current state.
  - Member+ read, owner/admin create.

**Status**: DELIVERED. 40 tests pass, ruff clean, migration 0027 at head.

### 16.2 — Read-Only Project Outcome Summary Endpoint ← DELIVERED 2026-06-21

**Lane: Standard (backend read-only aggregation).**

**Delivered shape**:

- Endpoint: `GET /groups/{gid}/projects/{pid}/outcome-summary` in `routers/projects.py`.
- Permission: member+ read via `get_membership_or_404`.
- Response (`PilotOutcomeSummaryResponse`):
  - `project`: id, name, business_goal, stage, status.
  - `latest_outcome`: latest `PilotOutcomeRecord` (id, title, created_at, decision_summary, risks, next_actions) or null.
  - `evidence_summary`: `OutcomeEvidenceCounts` — total_active, by_type dict, by_role dict from active `ProjectEvidenceLink` records.
  - `package_summary`: `OutcomePackageSummary` — count + latest `OutcomePackageInfo` (id, version, content_hash, quality_status, draft_count, created_at). No contract_json or source_draft_ids.
  - `runtime_summary`: `OutcomeRuntimeSummary` — total_operations from `OntologyRuntimeAudit`, last_operation dict (operation, outcome, created_at), note about v1 aggregation limits.
  - `decision_summary`/`risks`/`next_actions`: from latest_outcome, or empty string/empty arrays.
- No raw data exposure: no raw_answer, raw_prompt, source_path, storage_path, secret, token, password, stack_trace in any response field.
- No new tables, no migration. No POST/PATCH/DELETE — read-only.
- Existing `GET /projects/{pid}/summary` unchanged.
- Tests: 13 new tests in `TestOutcomeSummary` (member read, outsider 403, cross-group 404, null latest, uses latest, evidence counts by type/role, package summary, empty packages, runtime summary, forbidden keys, no side effects, per-project isolation, project fields). Combined 53/53 pass (40 from 16.1 + 13 from 16.2).
- **Design decisions resolved**:
  - New endpoint `/outcome-summary` on the projects router (not on outcomes router).
  - Auto-derives evidence/package/runtime sections from existing data; user-authored fields from latest_outcome.
  - Separate from `ProjectSummary` — outcome-summary is an FDE delivery view, not an operational summary.

### 16.3 — Pilot Delivery Report UI

**Lane: Standard**

In the Pilot workspace, add an outcome panel/report view that shows:
- Business goal (from project).
- Evidence summary: document evidence + saved RAG answers, counts by type.
- Model package: status, quality gate result, draft counts, contract hash.
- Validation state: PASS/WARN/FAIL with key findings.
- Key query result summaries: binding name, row count, last query timestamp.
- Risks: user-authored or auto-derived from validation warnings.
- Next actions: user-authored.

This is a working FDE handoff view, not a marketing page. It should look like
a professional deliverable, not a debug panel.

UI principles:
- Reuse existing Pilot workspace layout (goal stage expansion or new "Outcome"
  stage/tab).
- Swiss Style minimalism consistent with F2.
- Owner/admin see edit controls; members see read-only view.
- No raw data exposure.

Design decisions to resolve:
- Whether outcome is a new Pilot stage (stage 5: "Outcome") or a panel within
  the existing Pilot stage.
- Whether the report is a single scrollable page or tabbed sections.

### 16.4 — Exportable Interview/Demo Artifact

**Lane: Standard (if HTML/markdown) or Fast (if read-only display)**

Generate or display a concise delivery record suitable for demo/interview.
No PDF/export dependency unless already available; HTML/markdown first.

Expected shape:
- A single-page view (or printable HTML) that contains the full outcome record.
- Suitable for: sharing as a portfolio artifact, showing in an interview,
  handing to an FDE reviewer.
- Markdown export if the system already produces markdown; otherwise, styled
  HTML that prints cleanly.
- No external service dependency for PDF generation.

Design decisions to resolve:
- Markdown export (simple, already in the tech stack) vs. styled HTML page.
- Whether to add a "copy as markdown" button vs. a dedicated export route.
- Whether the export is a separate endpoint or a query parameter on the UI
  (`?export=1`).

## Hard Boundaries (repeated for implementation phase)

- No Graph RAG.
- No MCP runtime.
- No Agent auto-write.
- No external KB write.
- No autonomous publish.
- No new framework/dependency.
- No broad frontend redesign.
- No full PM system.
- No full reporting engine.
- No raw prompts, raw answers, secrets, or stack traces in any outcome surface.

## Product Alignment Check

| PRD principle | How Phase 16 honors it |
|---------------|------------------------|
| Ontology semantic operating layer north star | Outcome record proves the chain from fragmented knowledge to governed business decision |
| Every capability explainable in business/technical/risk/interview terms | Outcome record is the interview artifact — it IS the explanation |
| Agent is controlled coordination layer, not default answer | No Agent auto-write; outcome is user-authored or deterministically assembled |
| Group-scoped data isolation | Outcome record is group+project scoped, same isolation as all other resources |
| No speculative abstractions | Reuses existing project/evidence/package/runtime data; no new frameworks |

## Verification (Planning Phase)

- `scripts/check_doc_alignment.py` — confirm all docs reference Phase 16 planning.
- `git diff --check` — no whitespace errors.
- `git status --short` — only planning docs changed.
- No pytest, ruff, verify_ui, or e2e (no code changed).

## Open Decisions (resolved during implementation)

1. New `PilotOutcomeRecord` table vs. extending `BusinessProject` with outcome fields.
2. Immutable record vs. updatable (recommended: immutable after creation, like packages).
3. New Pilot stage ("Outcome") vs. panel within existing Pilot stage.
4. Markdown export vs. styled HTML page for interview artifact.
5. Whether to auto-derive evidence/package/query sections or require explicit user authoring.
