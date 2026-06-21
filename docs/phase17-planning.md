# Phase 17 Planning — FDE Demo Readiness & Operational Smoke v1

Status: PLANNING

## Decision

Phase 17 turns the delivered Phase 16 Pilot Outcome & FDE Delivery Record backend
into a **repeatable, verifiable demo** that a new user, interviewer, or FDE reviewer
can run end-to-end.

```text
seed pilot project
→ datasets upload + profiling
→ project evidence (RAG answers + document citations, user-confirmed)
→ modeling drafts → quality gates → model packages
→ runtime bindings → typed queries
→ outcome record (16.1) → outcome summary (16.2) → markdown artifact (16.4)
→ operational smoke confirms the full chain works, nothing leaks
```

This phase does NOT add new product capabilities. It makes the existing chain
**demonstrable without tribal knowledge** — a smoke script, a seed scenario,
an artifact quality gate, and an updated interview script.

## Why This Is Next

### The current gap

Phase 14–16 delivered the full backend chain:
group → project → dataset → evidence → model → package → runtime → outcome → artifact.

But demonstrating this chain today requires:
- Knowing which endpoints to call in which order.
- Manually seeding a project, uploading datasets, creating evidence links,
  building packages, running queries.
- Manually checking that the markdown artifact doesn't leak secrets.
- Knowing the interview narrative to explain why this isn't just a RAG app.

A new user or interviewer cannot see the value in 5 minutes. Phase 17 fixes that.

### How it fits the Ontology semantic operating layer north star

The north star is:

```text
fragmented knowledge → trusted evidence → governed entities/relationships
→ business objects, actions, permissions, Agent interfaces
→ enterprise Ontology semantic operating layer
```

Phase 17 doesn't build new Ontology features. It **proves the chain is real**
by making it reproducible. A smoke script that runs the full chain in 30 seconds
is more convincing than 66 passing tests on paper.

### Why this is higher priority than alternatives

| Alternative | Why deferred |
|-------------|--------------|
| Pilot workflow hardening (16.3 UI) | Backend chain works; UI is a frontend project, not a demo gap. |
| Ontology model operationalization | The modeling→package→runtime chain already works (Phase 13–14). Operationalizing it requires production data, not more code. |
| More RAG features / filters | The retrieval chain is stable. Demo value comes from the full chain, not incremental RAG tuning. |
| MCP runtime | Design exists. MCP is a future adapter, not a demo requirement. |
| Graph RAG | Governance graph exists (Phase 9). Graph RAG adds complexity without closing the demo gap. |
| Enterprise deployment | The project runs locally. Cloud deployment is a separate ops track, not a product gap. |

**Phase 17 makes the existing work demonstrable.** That's the highest-leverage
next step for a portfolio project.

## Product Alignment Check

| PRD principle | How Phase 17 honors it |
|---------------|------------------------|
| "Every capability must be explainable in business, technical, risk, and interview terms" | The demo script (17.4) is exactly that explanation |
| "A feature is not finished until it is runnable locally" | The smoke script (17.2) proves runnability |
| "Do not let future work drift into generic RAG" | The demo chain proves Ontology semantic layer, not just RAG |
| "Keep group-scoped data isolation as a hard invariant" | Seed scenario (17.1) uses isolated demo group |
| "No speculative abstractions" | No new features — just operational verification of what's built |

## Scope

### In scope

- **17.1 Demo seed scenario contract**: Define a manufacturing-equipment or
  generic business pilot seed scenario. Specify project name, business goal,
  dataset shape (small CSV/XLSX, 5–10 rows), expected evidence, expected
  package quality, expected artifact content. No real sensitive data.
- **17.2 Backend operational smoke script**: A Python script
  (`scripts/smoke_fde_demo.py`) that calls the full chain via the API:
  register → create group → create project → upload dataset → create evidence
  links → build model packages → generate bindings → run query → create
  outcome record → fetch JSON summary → fetch markdown artifact. Returns
  pass/fail with per-step details.
- **17.3 Artifact quality gate**: A validation function or script that checks
  the generated markdown artifact for:
  - Contains required sections (business goal, evidence, package, runtime, provenance).
  - Does NOT contain forbidden terms (raw_content, raw_answer, source_path,
    storage_path, secret, token, password, stack_trace).
  - Decision/risks/next_actions are present when an outcome record exists.
  - Returns pass/fail with specific violations listed.
- **17.4 Interview/demo script refresh**: Update
  `docs/interview-demo-questions.md` with:
  - Phase 16 FDE delivery narrative.
  - How the smoke script proves the chain.
  - Why Graph RAG, MCP runtime, and Agent auto-write are intentionally deferred.
  - The Ontology semantic operating layer north star with Phase 14–16 evidence.
- **17.5 Phase 17 closeout review**: Verify smoke script passes, artifact gate
  passes, docs aligned, no regressions.

### Out of scope (hard boundaries)

- No frontend UI changes.
- No PDF/HTML report engine.
- No MCP runtime.
- No Graph RAG.
- No Agent auto-write.
- No external KB auto-repair.
- No production deployment overhaul.
- No new database tables or migrations.
- No new API endpoints (except possibly a convenience endpoint if trivial).
- No new framework or dependency.
- No real enterprise data in the seed scenario.

## Suggested Slices

### 17.1 — Demo Seed Scenario Contract

**Lane: Fast (design doc only).**

Define the demo scenario:

| Field | Value |
|-------|-------|
| Project name | "FDE Demo — Equipment Monitoring Pilot" |
| Business goal | "Build an ontology for manufacturing equipment monitoring to reduce unplanned downtime." |
| Entry mode | `problem_first` |
| Industry template | `manufacturing` |
| Dataset | Small CSV: 5–10 rows of equipment records with columns like equipment_id, name, type, status, last_maintenance_date, sensor_count. No PII, no real production data. |
| Expected evidence | 2–3 RAG answers saved as project evidence; 1–2 document evidence links. |
| Expected modeling drafts | 2–4 drafts (object_type: Equipment, properties: name/type/status/sensor_count). |
| Expected package quality | PASS or WARN (no FAIL). |
| Expected runtime query | 1 binding, 1 query returning 5–10 rows. |
| Expected outcome | 1 PilotOutcomeRecord with decision "Proceed to production pilot with expanded dataset." |
| Expected artifact | Contains all required sections, no forbidden terms. |

The contract is a markdown doc (`docs/phase17-seed-contract.md`) or a section
in the planning doc. It serves as the spec for 17.2 (smoke script) and 17.3
(artifact gate).

### 17.2 — Backend Operational Smoke Script

**Lane: Standard (Python script + tests).**

A single script: `scripts/smoke_fde_demo.py`.

Requirements:
- Calls the full chain via the API (using `requests` or `httpx`, whichever
  the project already uses for smoke tests).
- Step-by-step with clear pass/fail per step.
- Uses a dedicated demo group (isolated from real data).
- Cleans up or uses idempotent creation so it's re-runnable.
- Returns exit code 0 on full pass, 1 on any step failure.
- Prints per-step timing for latency visibility.
- Does NOT require real LLM/embedding calls if fake provider can be used;
  falls back to real provider if configured.

Steps:
```
1. Register demo user
2. Create demo group
3. Create pilot project (goal stage)
4. Upload seed dataset (advance to data stage)
5. Generate modeling drafts from dataset (advance to model stage)
6. Review drafts (accept)
7. Build package (advance to validate stage)
8. Generate bindings (advance to pilot stage)
9. Run pilot query
10. Create outcome record
11. Fetch outcome-summary JSON
12. Fetch outcome-artifact.md
13. Run artifact quality gate (17.3)
14. Print summary: PASS/FAIL with per-step results
```

### 17.3 — Artifact Quality Gate

**Lane: Standard (validation function + tests).**

A pure function or small class that validates a markdown artifact string.

Input: the markdown string from `GET /outcome-artifact.md`.

Checks:
1. Contains `# ` heading with project name.
2. Contains `## Business Goal` section with non-empty content.
3. Contains `## Evidence Summary` section.
4. Contains `## Ontology Package Summary` section.
5. Contains `## Runtime Summary` section.
6. Contains `## Provenance` section.
7. Does NOT contain forbidden substrings: `raw_content`, `raw_answer`,
   `source_path`, `storage_path`, `secret` (as standalone word in
   non-provenance context), `stack_trace` (as standalone word in
   non-provenance context), `password`.
8. If outcome record exists, `## Latest Outcome` section has decision/risks/actions.
9. If no outcome record, `Not recorded yet` appears in Latest Outcome section.

Returns: `(passed: bool, violations: list[str])`.

Location: `src/semantic_lighthouse/services/artifact_quality.py` or
`scripts/check_artifact_quality.py` depending on whether it's backend
or standalone. Prefer backend service if it fits the existing pattern;
otherwise standalone script.

### 17.4 — Interview/Demo Script Refresh

**Lane: Fast (docs only).**

Update `docs/interview-demo-questions.md`:
- Add Phase 16 FDE delivery narrative section.
- Add smoke script demo flow (what to show, what to say).
- Update "why not Graph RAG / MCP / Agent auto-write" with current state.
- Update north star narrative with Phase 14–16 chain evidence.
- Keep existing Phase 8–13 demo content intact.

### 17.5 — Phase 17 Closeout Review

**Lane: Standard (review).**

Verify:
- Smoke script passes locally.
- Artifact quality gate passes on smoke output.
- Markdown artifact passes quality gate checks.
- Docs aligned (`check_doc_alignment.py`).
- 66 existing Phase 16 tests still pass (no regressions).
- Ruff clean on changed files.
- No migration drift.

## Hard Boundaries

- No frontend UI changes.
- No PDF/HTML report engine.
- No MCP runtime.
- No Graph RAG.
- No Agent auto-write.
- No external KB auto-repair.
- No production deployment overhaul.
- No new database tables or migrations (unless a trivial convenience migration
  is unavoidable).
- No new framework or dependency beyond what's already in `requirements.txt`.
- No real enterprise data in seed scenario.
- No raw prompts, raw answers, paths, secrets, or stack traces in any demo output.

## Verification (Planning Phase)

- `scripts/check_doc_alignment.py` — confirm all docs reference Phase 17 planning.
- `git diff --check` — no whitespace errors.
- `git status --short` — only planning docs changed.
- No pytest, ruff, verify_ui, or e2e (no code changed).

## Open Decisions (resolved during implementation)

1. Seed scenario: manufacturing equipment vs. generic ecommerce vs. other domain.
2. Smoke script: fake provider vs. real LLM calls (fake preferred for speed).
3. Artifact quality gate: backend service vs. standalone script.
4. Whether to add a convenience `POST /demo/seed` endpoint or keep seeding manual.
5. Whether 17.3 artifact gate runs as part of smoke script or as a pytest.
