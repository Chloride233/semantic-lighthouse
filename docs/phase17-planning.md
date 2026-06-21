# Phase 17 Planning — FDE Demo Readiness & Operational Smoke v1

Status: 17.1–17.4 DELIVERED — 17.5 closeout review pending.

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

### 17.1 — Demo Seed Scenario Contract ← SPEC DETAILED 2026-06-21

**Lane: Fast (design doc only). Implementation pending.**

This section is the authoritative spec for the Phase 17 seed demo. It defines
exactly what the smoke script (17.2) must create and what the artifact gate
(17.3) must verify. No real data — all values are synthetic and non-sensitive.

#### 17.1.1 — Demo Identity

| Field | Value |
|-------|-------|
| Domain | **Manufacturing — maintenance workflow & equipment reliability** |
| Rationale | Manufacturing has clear business objects (Equipment, WorkOrder, Site, Team), structured datasets with timestamps, and a defensible "reduce downtime" business goal. More convincing than ecommerce for an enterprise FDE demo. |
| Demo user email | `demo-operator@fde.local` |
| Demo user display_name | `Demo Operator` |
| Demo group name | `FDE Demo — Manufacturing` |
| Project name | `Equipment Reliability Pilot — Plant 3` |
| Entry mode | `problem_first` |
| Industry template | `manufacturing` |

#### 17.1.2 — Business Goal

```
Build a governed ontology for manufacturing equipment and work-order management
at Plant 3 to reduce unplanned downtime by improving failure-code traceability
and maintenance-team assignment accuracy.
```

This goal is specific enough to produce named business objects, has measurable
intent ("reduce downtime"), and ties to a real enterprise problem domain.

#### 17.1.3 — Seed Dataset: `plant3_work_orders.csv`

Minimum 8 rows, 12 columns. All values synthetic. No PII, no real production
data, no real equipment serial numbers.

| Column | Type | Example | Notes |
|--------|------|---------|-------|
| `equipment_id` | string | `EQ-301`, `EQ-302` | FK to Equipment object type |
| `work_order_id` | string | `WO-1001`, `WO-1002` | Primary record key |
| `asset_type` | string | `CNC Lathe`, `Injection Molder`, `Conveyor` | Controlled vocabulary, 4–5 values |
| `site` | string | `Plant 3` | All rows same site for pilot scope |
| `priority` | string | `Critical`, `High`, `Medium`, `Low` | Controlled vocabulary |
| `status` | string | `Open`, `In Progress`, `Closed` | Workflow state |
| `opened_at` | ISO 8601 datetime | `2026-05-01T08:30:00` | |
| `closed_at` | ISO 8601 datetime or empty | `2026-05-03T14:00:00` | Empty if status != Closed |
| `downtime_hours` | float | `2.5`, `18.0` | Derived: closed_at - opened_at |
| `owner_team` | string | `Mech Maintenance`, `Elec Maintenance`, `Ops` | FK to Team object type |
| `failure_code` | string | `BRG-01`, `MTR-03`, `CTL-07` | Categorical with 6–8 codes |
| `resolution_note` | string, max 200 chars | `Replaced bearing assembly.` | Short free-text |

No column contains: real names, real serial numbers, real locations, PII, PHI,
financial data, passwords, secrets, or API keys.

#### 17.1.4 — Ontology Business Objects

##### Object Types

| API Name | Display Name | Description | Key Properties |
|----------|-------------|-------------|----------------|
| `equipment` | Equipment | A physical asset at Plant 3 monitored by the ontology | equipment_id (PK), asset_type, site, status, sensor_count, installed_date |
| `work_order` | Work Order | A maintenance or repair work order against equipment | work_order_id (PK), priority, status, opened_at, closed_at, downtime_hours, failure_code, resolution_note |
| `site` | Site | A manufacturing facility | site_code (PK), site_name, location_city, active |
| `team` | Maintenance Team | A team responsible for equipment maintenance | team_code (PK), team_name, specialty, shift |

##### Properties (minimum set)

**Equipment**: `equipment_id` (string, PK), `asset_type` (string, enum), `site` (string), `status` (string, enum: Active/Maintenance/Retired), `sensor_count` (int), `installed_date` (date).

**WorkOrder**: `work_order_id` (string, PK), `priority` (string, enum), `status` (string, enum), `opened_at` (datetime), `closed_at` (datetime, nullable), `downtime_hours` (float), `failure_code` (string), `resolution_note` (string).

**Site**: `site_code` (string, PK), `site_name` (string), `location_city` (string), `active` (bool).

**Team**: `team_code` (string, PK), `team_name` (string), `specialty` (string, enum: Mechanical/Electrical/Operations), `shift` (string).

##### Link Types

| Source | Target | Relationship | Cardinality |
|--------|--------|-------------|-------------|
| `work_order` | `equipment` | `work_order_targets_equipment` | many-to-one |
| `work_order` | `team` | `work_order_assigned_to_team` | many-to-one |
| `equipment` | `site` | `equipment_located_at_site` | many-to-one |
| `team` | `site` | `team_based_at_site` | many-to-one |

##### Action Types (if implemented)

| API Name | Display Name | Required Role | Description |
|----------|-------------|---------------|-------------|
| `reassign_work_order` | Reassign Work Order | admin | Change the owner_team on an open work order |

#### 17.1.5 — Evidence Plan

| # | Evidence Type | Role | Description |
|---|--------------|------|-------------|
| 1 | `document` | `context` | KB document describing Plant 3 equipment taxonomy and failure-code catalog. Simulates an existing enterprise knowledge asset. |
| 2 | `document` | `requirement` | KB document with maintenance SLA policy (response-time targets by priority). |
| 3 | `rag_run` | `decision` | User asks: "What failure codes are most correlated with downtime over 8 hours?" System returns RAG answer citing the taxonomy doc. User saves as evidence. |

Evidence links must all be `active` status. No raw answers, prompts, or file
paths exposed in evidence provenance.

#### 17.1.6 — Expected Modeling Output

| Item | Expected Value | Notes |
|------|---------------|-------|
| Object Type drafts | 4 (Equipment, WorkOrder, Site, Team) | Generated from dataset profiling + KB documents |
| Property drafts | 12–16 across all object types | 3–5 per object type |
| Link Type drafts | 3–4 | equipment↔site, work_order↔equipment, work_order↔team, team↔site |
| Action Type drafts | 0–1 (optional) | `reassign_work_order` if scaffolded |
| Accepted drafts | All proposed drafts | Via batch review |
| Package build | 1 package | `quality_status` must be PASS or WARN (FAIL blocks demo) |
| Runtime bindings | 1 binding per object type with matching dataset columns (min 2) | equipment↔dataset, work_order↔dataset |
| Runtime query | 1 query returning ≥5 rows | Example: "All work orders with priority=Critical and status=Open" |

#### 17.1.7 — Outcome Record

| Field | Value |
|-------|-------|
| `title` | `Plant 3 Equipment Reliability — FDE Delivery v1` |
| `decision_summary` | `The Plant 3 equipment ontology pilot identified bearing-related failure codes (BRG-01, BRG-03) as the top contributors to unplanned downtime, accounting for 62% of critical work orders. Proceed to production pilot with expanded dataset covering Plants 1–4 and integrate real-time sensor feeds.` |
| `risks` | `["Seed dataset limited to 8 synthetic rows — production distribution may differ", "Failure code taxonomy may be incomplete for electrical failures", "Sensor-count property not yet validated against real SCADA data"]` |
| `next_actions` | `["Expand dataset to Plants 1–4 with real equipment registries", "Validate failure-code catalog against 12 months of CMMS history", "Integrate real-time sensor feed for predictive maintenance modeling", "Present findings to Plant 3 operations director"]` |
| `selected_evidence_refs` | 3 evidence links (2 document + 1 rag_run) |
| `package_refs` | 1 package reference |

#### 17.1.8 — Expected Markdown Artifact

The artifact must:
- Contain all 7 required sections per 17.3 spec.
- Show `Total Active Evidence Links: 3` (or matching evidence plan count).
- Show `Total Packages: 1` with PASS or WARN quality status.
- Show `Total Operations` ≥ 2 (bindings + query).
- Include the decision summary, risks, and next actions from the outcome record.
- Pass all 17.3 quality gate checks with zero violations.
- Be ≤ 5 KB in size (well under the 20 KB max).

#### 17.1.9 — Data Safety Notes

- **All dataset values are synthetic.** No real equipment IDs, no real plant
  names, no real failure codes, no real CMMS data.
- No PII, PHI, financial data, credentials, secrets, or API keys in any seed
  data.
- The demo group is fully isolated — no cross-group data leakage possible.
- The smoke script (17.2) may optionally tear down the demo group after
  completion, or leave it for inspection.

### 17.2 — Backend Operational Smoke Script ← DELIVERED 2026-06-21

**Lane: Standard (Python script).**

**Delivered shape**:

- Script: `scripts/smoke_fde_demo.py` — 11 steps, runs in ~1.3s on temp SQLite.
- Uses FastAPI TestClient (in-process, no uvicorn, no real network).
- Fake providers for embedding and chat (no API keys needed).
- Direct DB seed for heavy parts (documents, evidence links, packages, runtime audit).
- Public API calls for: register, login, group create, project create, outcome create,
  outcome-summary GET, outcome-artifact.md GET.
- Inline artifact quality gate (`validate_artifact()`) per 17.3 spec.
- Auto-creates temp DB at `.tmp/smoke-fde-demo.db`, cleans up on exit.
- Exit code 0 on pass, 1 on failure.
- Step-by-step PASS/FAIL with per-step timing.

**Smoke output (2026-06-21)**:
```
  [PASS] register (1.02s)
  [PASS] login (1.20s)
  [PASS] create_group (1.21s)
  [PASS] create_project (1.23s)
  [PASS] seed_evidence (1.23s) — 2 docs + 1 rag_run + 3 evidence links
  [PASS] seed_package (1.23s) — 1 package v1 PASS (4 drafts)
  [PASS] seed_runtime (1.23s) — 2 audit records (bindings + query, 8 rows)
  [PASS] create_outcome (1.26s) — Plant 3 Equipment Reliability v1
  [PASS] outcome_summary (1.26s) — evidence=3 pkg=1 runtime=2 outcome=yes
  [PASS] outcome_artifact (1.27s) — 1911B text/markdown
  [PASS] artifact_quality_gate (1.27s) — PASS (0 findings)
FDE Demo Smoke: PASS  |  Steps: 11  Passed: 11  Failed: 0  |  Artifact gate: PASS
```

Run command: `.venv/Scripts/python scripts/smoke_fde_demo.py`

### 17.3 — Artifact Quality Gate ← SPEC DETAILED 2026-06-21

**Lane: Standard (implementation pending — spec only this round).**

This section defines the exact validation contract for a generated markdown
artifact. This spec is input to the smoke script (17.2 step 13) and may be
implemented as a standalone Python function or pytest helper. No implementation
this round.

#### 17.3.1 — Function Signature (Recommended)

```python
def validate_artifact(artifact_md: str) -> tuple[bool, str, list[str]]:
    """Validate a Pilot Outcome markdown artifact.

    Returns:
        (passed, status, findings)
        passed: bool — True if no FAIL-level violations.
        status: str — "PASS" | "WARN" | "FAIL".
        findings: list[str] — human-readable violation messages.
    """
```

Alternative location for smoke script use: `scripts/check_artifact_quality.py`
with the same signature, called as a subprocess or imported.

#### 17.3.2 — Required Sections

The artifact must contain all seven of these markdown headings. Missing
section → **FAIL**.

| # | Required Heading | Notes |
|---|-----------------|-------|
| 1 | `# <project_name> — Pilot Outcome / FDE Delivery Record` | Level-1 heading with project name. |
| 2 | `## Business Goal` | Must be followed by non-whitespace content. |
| 3 | `## Latest Outcome` | Must exist even if content is "Not recorded yet." |
| 4 | `## Evidence Summary` | Must contain `Total Active Evidence Links`. |
| 5 | `## Ontology Package Summary` | Must contain `Total Packages`. |
| 6 | `## Runtime Summary` | Must contain `Total Operations`. |
| 7 | `## Provenance` | Must contain "group-scoped project summary" or equivalent. |

#### 17.3.3 — Required Business Signals

Beyond section existence, the artifact must carry minimum business meaning.
Failure → **WARN** (not FAIL — a demo with small data may still be valid).

| # | Signal | Threshold | Severity |
|---|--------|-----------|----------|
| 1 | `business_goal` non-empty | Text length > 10 chars after stripping | WARN |
| 2 | `total_active` evidence > 0 | ≥ 1 evidence link | WARN |
| 3 | `count` packages > 0 | ≥ 1 ontology package | WARN |
| 4 | `total_operations` runtime > 0 | ≥ 1 runtime operation | WARN |
| 5 | `decision_summary` non-empty (when outcome exists) | Text length > 20 chars after stripping | WARN |
| 6 | `risks` non-empty list (when outcome exists) | ≥ 1 risk entry | WARN |
| 7 | `next_actions` non-empty list (when outcome exists) | ≥ 1 next action entry | WARN |
| 8 | `latest_outcome` not null | Outcome record exists | WARN |

A WARN result means "artifact exists and is structurally valid, but some
business signals are weak or absent." This is acceptable for a pilot with
minimal seed data. The smoke script may report WARN as a soft pass.

#### 17.3.4 — Forbidden Terms

Any occurrence of these substrings (case-insensitive) in the artifact body →
**FAIL**. This is a hard security boundary.

| # | Forbidden Term | Rationale |
|---|---------------|-----------|
| 1 | `raw_content` | Raw document text must never leak into artifact |
| 2 | `raw_answer` | Raw LLM answer text must never leak |
| 3 | `raw_prompt` | Raw LLM prompt must never leak |
| 4 | `answer` | Standalone "answer" key from RAG response JSON — must not appear outside provenance context |
| 5 | `prompt` | Standalone "prompt" key — must not appear outside provenance context |
| 6 | `source_path` | File paths to source documents must never leak |
| 7 | `storage_path` | File paths to stored datasets must never leak |
| 8 | `secret` | Any credential or secret string |
| 9 | `token` | JWT or API token |
| 10 | `password` | Any password field |
| 11 | `stack_trace` | Python traceback or error stack |

**Provenance section exemption**: The provenance section may legitimately
declare what the artifact does NOT contain (e.g., "does not contain raw
prompts, raw answers, file paths, secrets, tokens, or stack traces").
The validator should either:
- Skip the Provenance section when checking forbidden terms, OR
- Check that forbidden terms only appear in negated/declarative context
  within the Provenance section.

Recommended approach: skip the `## Provenance` section when scanning for
forbidden terms. Simpler and less error-prone.

#### 17.3.5 — Boundedness Rules

| # | Rule | Threshold | Severity |
|---|------|-----------|----------|
| 1 | Max artifact size | ≤ 20,000 bytes (≈20 KB) | FAIL |
| 2 | No raw dataset rows | Must not contain comma-separated values matching the seed dataset pattern (e.g., lines with ≥10 comma-separated fields) | FAIL |
| 3 | No local file paths | Must not contain patterns like `/data/`, `C:\`, `\\\\`, `/tmp/`, `/home/`, `/Users/` | FAIL |
| 4 | No JSON object blobs | Must not contain `{` ... `}` with keys matching `answer`, `raw_content`, `source_path` | FAIL |
| 5 | No stack-like text | Must not contain `File "`, `line `, `Traceback (most recent call last)` | FAIL |

The 20 KB limit is generous — a well-formed artifact with the 17.1 seed
scenario should be under 5 KB. The limit exists to catch catastrophic
leakage (e.g., raw CSV output dumped into the artifact).

#### 17.3.6 — Output Format

The validation function returns a three-tuple:

```python
(passed: bool, status: str, findings: list[str])
```

| status | Meaning | Exit Code (if CLI) |
|--------|---------|-------------------|
| `PASS` | All required sections present, no forbidden terms, all boundedness rules pass, business signals ≥ minimum thresholds. | 0 |
| `WARN` | All FAIL-level checks pass, but one or more WARN-level business signals are below threshold. | 0 (soft pass for smoke) |
| `FAIL` | One or more FAIL-level checks violated: missing section, forbidden term found, boundedness rule broken. | 1 |

Each finding string follows the format: `[{severity}] {section}: {message}`.
Examples:
- `[FAIL] forbidden_terms: found 'source_path' outside Provenance section`
- `[WARN] business_signals: evidence total_active is 0`
- `[FAIL] boundedness: artifact size 28431 bytes exceeds 20000 byte limit`
- `[FAIL] required_sections: missing '## Runtime Summary'`

#### 17.3.7 — Implementation Notes (For 17.2 Reference)

- This spec is designed to be implementable as a single-file Python module
  with zero dependencies beyond the standard library.
- The validator should NOT import from `semantic_lighthouse.*` to avoid
  coupling to the backend. It operates on raw markdown strings.
- Location preference: `scripts/check_artifact_quality.py` (standalone,
  callable by smoke script or manually on any `.md` file).
- The smoke script (17.2 step 13) will call this validator on the
  `GET /outcome-artifact.md` response text and report PASS/WARN/FAIL.
- A follow-up task may add pytest coverage for the validator itself, but
  the validator is a script, not a backend service — no FastAPI dependency.

### 17.4 — Interview/Demo Script Refresh ← DELIVERED 2026-06-21

**Lane: Fast (docs only).**

**Delivered shape**:

- Updated `docs/interview-demo-questions.md` with Phase 14–17 FDE Demo section:
  - "What Semantic Lighthouse Is (and Isn't)" — Ontology positioning vs RAG/Agent
  - FDE user business flow — 11-step chain from registration to markdown artifact
  - Why manufacturing equipment reliability seed (not ecommerce)
  - Full chain architecture diagram (Phase 14 → 16.1 → 16.2 → 16.4 → 17.2 → 17.3)
  - FDE deliverables table (Outcome Record / Outcome Summary / Markdown Artifact)
  - Smoke script proof: command, output, 11/11 PASS, ~0.8s
  - Risk boundaries table (7 rows: no auto-write, no data leak, no Graph RAG, no MCP, no UI refactor, no real data, no cloud deploy)
  - Engineering value table (6 rows: group isolation, auditable evidence, bounded artifact, deterministic backend, HITL boundary, immutable outcome)
- Five-Minute Demo Script with per-phase timing (0:00–4:00)
- FAQ section: 5 common questions with full answers
  - vs RAG
  - vs Knowledge Graph demo
  - Why not Agent auto-modeling
  - Why read-only runtime/smoke first
  - Scaling to real enterprise data
- Deprecated old "Two-Minute Demo Script" and "Phase 9 Teaser (Planned)" → replaced with delivered Phase 9–13 summary

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

## Open Decisions

1. Seed scenario: **RESOLVED** — manufacturing equipment maintenance & work-order
   reliability (see 17.1.1). Not ecommerce.
2. Smoke script: fake provider vs. real LLM calls — **open**. Fake preferred for
   speed and offline demo; real provider fallback if configured.
3. Artifact quality gate: **RESOLVED** — standalone script at
   `scripts/check_artifact_quality.py` with zero backend coupling.
4. Convenience `POST /demo/seed` endpoint — **deferred** to post-17.2 decision.
   Smoke script will call existing endpoints directly.
5. 17.3 artifact gate integration: **RESOLVED** — called as a subprocess or
   import by smoke script step 13. May also have pytest coverage added later.
