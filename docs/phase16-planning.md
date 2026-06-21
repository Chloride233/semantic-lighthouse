# Phase 16 Planning — Pilot Outcome & FDE Delivery Record v1

Status: PLANNING

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

### 16.1 — Outcome Record Design / Schema Boundary

**Lane: Fast (design) → Standard (if migration needed)**

Decide whether to reuse existing project/package/query audit data first.
No migration unless implementation proves a durable table is required.

Design fields for a future outcome record:

| Field | Source | Notes |
|-------|--------|-------|
| `project_id` | `BusinessProject.id` | FK, the pilot this record describes |
| `business_goal_snapshot` | `BusinessProject.goal_statement` | Immutable copy at record creation time |
| `selected_evidence_refs` | `ProjectEvidenceLink` | Bounded provenance — no raw prompts, answers, paths |
| `package_id` | `OntologyModelPackage.id` | The quality-gated model package produced |
| `query_refs` | `OntologyRuntimeAudit` | Key query result summaries, not raw CSV |
| `decision_summary` | User-authored | What the enterprise should conclude |
| `risks` | User-authored | Known limitations, confidence gaps, data quality issues |
| `next_actions` | User-authored | Recommended follow-up work |
| `created_by` | `User.id` | Who authored the outcome record |
| `created_at` | timestamp | Immutable creation time |

Design decisions to resolve:
- Reuse existing tables vs. new `PilotOutcomeRecord` table.
- Whether the outcome record is immutable (recommended: yes, like packages).
- Whether to snapshot referenced artifacts at record creation time.
- Whether member can read, or only owner/admin can create (recommended:
  member+ read, owner/admin create).

### 16.2 — Read-Only Project Outcome Summary Endpoint

**Lane: Standard**

Reuse existing `ProjectSummary`, packages, runtime audit/query outputs where
possible. Build a single endpoint that assembles the outcome view from existing
data without duplicating business logic.

Expected shape:
- `GET /groups/{gid}/projects/{pid}/outcome` — member+ read.
- If write is needed: `POST /groups/{gid}/projects/{pid}/outcome` — owner/admin
  create or update (idempotent: one outcome per project).
- Response assembles: goal snapshot, evidence summary (type, role, count),
  package summary (status, hash, draft counts), latest runtime query summary
  (binding status, sample row count, query timestamp), decision/risks/next_actions
  (if authored).
- No raw dataset paths, raw prompts, raw answers, secrets, or stack traces.

Design decisions to resolve:
- Whether to reuse `GET /projects/{pid}/summary` vs. a new endpoint.
- Whether to auto-derive sections from existing data (evidence, packages, queries)
  or require explicit user-authored fields.
- Whether the outcome is a separate resource or an extended project summary.

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
