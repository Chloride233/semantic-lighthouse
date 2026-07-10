# Semantic Lighthouse

[Chinese](README.zh-CN.md) | [English](README.md)

Semantic Lighthouse is an **ontology-oriented semantic operating layer workspace** for enterprise AI transformation. It shows how fragmented documents, knowledge, datasets, workflows, permissions, evidence, and Agent-facing interfaces can be turned into an auditable business semantic layer.

This is not a generic RAG chatbot and not an autonomous Agent platform. The core claim is narrower and stronger:

> Enterprise AI needs governed business semantics, not just model calls.

## What It Proves

Semantic Lighthouse demonstrates an end-to-end FDE-style delivery chain:

```text
business goal
-> scoped evidence
-> reviewed ontology model
-> quality-gated package
-> dataset binding
-> typed runtime query
-> outcome record
-> bounded markdown artifact
-> ontology governance feedback
```

The strongest current demo is the manufacturing ontology pipeline from Phase 19:

```text
CSV
-> manifest.json
-> mapping_contract.json
-> rule_validation_report.json
-> governance_feedback.json
-> FDE smoke demo
```

## Run The Demo

Generate a realistic synthetic manufacturing data pack:

```powershell
.\.venv\Scripts\python scripts\generate_manufacturing_dataset.py `
    --preset tiny --output-dir .tmp\phase19-manufacturing
```

Run the full FDE smoke chain against that data pack:

```powershell
.\.venv\Scripts\python scripts\smoke_fde_demo.py `
    --data-pack .tmp\phase19-manufacturing
```

Expected result:

```text
FDE Demo Smoke: PASS | 11/11
Artifact gate: PASS
```

The smoke uses fake embedding/chat providers, temporary SQLite, and no external API keys.

## Phase 19 Ontology Pipeline

Run the full offline Semantic CI gate:

```powershell
.\.venv\Scripts\python scripts\run_semantic_ci.py `
    --data-pack .tmp\phase19-manufacturing
```

This writes `semantic_ci_report.json` with gate status, artifact hashes, governance candidate counts, and the human-review boundary.

Build a reviewer-facing packet for the governance candidates:

```powershell
.\.venv\Scripts\python scripts\build_governance_review_packet.py `
    --data-pack .tmp\phase19-manufacturing
```

For an AdventureWorks benchmark, first export the focused raw pack, map it into
the manufacturing contract, then run Semantic CI:

```powershell
.\.venv\Scripts\python scripts\export_adventureworks.py `
    --ssh-target ubuntu@<server-ip> `
    --output .tmp\adventureworks

.\.venv\Scripts\python scripts\map_adventureworks_to_semantic_pack.py `
    --input .tmp\adventureworks `
    --output .tmp\adventureworks-semantic

.\.venv\Scripts\python scripts\run_semantic_ci.py `
    --data-pack .tmp\adventureworks-semantic `
    --regenerate-mapping --allow-critical

.\.venv\Scripts\python scripts\build_governance_review_packet.py `
    --data-pack .tmp\adventureworks-semantic

.\.venv\Scripts\python scripts\build_adventureworks_ontology_seed.py `
    --data-pack .tmp\adventureworks-semantic

.\.venv\Scripts\python scripts\build_governance_review_workspace.py `
    --data-pack .tmp\adventureworks-semantic

.\.venv\Scripts\python scripts\build_governance_decision_template.py `
    --data-pack .tmp\adventureworks-semantic

.\.venv\Scripts\python scripts\build_governance_decision_csv.py `
    --data-pack .tmp\adventureworks-semantic

.\.venv\Scripts\python scripts\build_governance_review_briefing.py `
    --data-pack .tmp\adventureworks-semantic

.\.venv\Scripts\python scripts\build_governance_review_workbench.py `
    --data-pack .tmp\adventureworks-semantic

.\.venv\Scripts\python scripts\inspect_governance_decision_csv.py `
    --csv .tmp\adventureworks-semantic\governance_review_decisions_template.csv

.\.venv\Scripts\python scripts\fill_governance_decision_csv.py `
    --csv .tmp\adventureworks-semantic\governance_review_decisions_template.csv `
    --source-table equipment `
    --derived-class at_risk_equipment `
    --decision defer `
    --reviewer ontology_steward `
    --reviewed-at 2026-07-09T08:00:00+00:00 `
    --rationale "Needs explicit equipment domain owner review."

.\.venv\Scripts\python scripts\convert_governance_decision_csv.py `
    --csv .tmp\adventureworks-semantic\governance_review_decisions_template.csv `
    --output .tmp\adventureworks-semantic\governance_review_decisions.json `
    --review-batch pilot-review

.\.venv\Scripts\python scripts\precheck_governance_review_decisions.py `
    --data-pack .tmp\adventureworks-semantic `
    --decisions .tmp\adventureworks-semantic\governance_review_decisions.json

.\.venv\Scripts\python scripts\apply_governance_review_decisions.py `
    --data-pack .tmp\adventureworks-semantic

.\.venv\Scripts\python scripts\build_accepted_ontology_drafts.py `
    --data-pack .tmp\adventureworks-semantic

.\.venv\Scripts\python scripts\build_offline_model_package.py `
    --data-pack .tmp\adventureworks-semantic

.\.venv\Scripts\python scripts\build_offline_dataset_binding.py `
    --data-pack .tmp\adventureworks-semantic

.\.venv\Scripts\python scripts\build_offline_runtime_query_plan.py `
    --data-pack .tmp\adventureworks-semantic

.\.venv\Scripts\python scripts\build_semantic_asset_feedback.py `
    --data-pack .tmp\adventureworks-semantic

.\.venv\Scripts\python scripts\build_offline_acceptance_report.py `
    --data-pack .tmp\adventureworks-semantic
```

The ontology seed writes `adventureworks_ontology_seed.json` and
`adventureworks_ontology_seed.md`. It is an offline review artifact only:
object types, FK relationship candidates, and derived-class candidates still
require human review before model package publication or runtime use.
The review workspace writes pending decision records for governance candidates
without applying model changes or creating real governance issues.
The decision template writes `governance_review_decisions_template.json` for
human editing. It is not ready for apply until a reviewer fills decision,
reviewer, reviewed_at, and rationale fields and saves the result as
`governance_review_decisions.json`.
For spreadsheet-style review, the CSV template writes
`governance_review_decisions_template.csv`. Fill the same decision fields in
the CSV, then convert it to `governance_review_decisions.json` before running
precheck. Blank decision rows are skipped so partial review can be prechecked.
`inspect_governance_decision_csv.py` reports whether the filled CSV is complete
enough for the post-review runner and lists missing decision fields by row.
`build_governance_review_briefing.py` groups pending review items by source
table and derived class, with bounded source row samples for explicit review.
`build_governance_review_workbench.py` renders the same review data as a static
offline HTML workbench and exports a filled decision CSV from the browser.
`fill_governance_decision_csv.py` can write selected rows when a reviewer has
already made an explicit decision; it requires at least one filter and does not
infer or auto-accept candidates.
For public benchmark continuation only, `build_public_benchmark_decisions.py`
can generate fixture decisions from the review workspace. This is explicitly
not enterprise human review; it exists to exercise the offline chain with
public sample data while keeping database writes, package publication, and
runtime execution out of scope.
The decision precheck validates the filled decision file before apply. It
returns `FAIL` for unknown IDs, invalid decisions, missing reviewer,
reviewed_at, or required rationale, and writes no accepted changes.
After precheck passes, `run_post_review_semantic_loop.py` can run the offline
post-review chain in one command: apply decisions, build accepted drafts,
build the offline package, bind datasets, generate runtime dry-run plans,
build semantic asset feedback, and write the acceptance report. It still does
not write to the database, publish packages, activate runtime, or auto-accept
candidates.
The runner requires the decision precheck to return `PASS`; incomplete CSV rows
are caught by CSV inspection before conversion, so the runner stops before
writing `governance_review_decisions.json`.

```powershell
.\.venv\Scripts\python scripts\run_post_review_semantic_loop.py `
    --data-pack .tmp\adventureworks-semantic `
    --decision-csv .tmp\adventureworks-semantic\governance_review_decisions_template.csv `
    --review-batch pilot-review
```

For a public benchmark fixture run, generate explicit fixture decisions before
the post-review loop:

```powershell
.\.venv\Scripts\python scripts\build_public_benchmark_decisions.py `
    --data-pack .tmp\adventureworks-semantic `
    --benchmark-name "AdventureWorks public benchmark"

.\.venv\Scripts\python scripts\run_post_review_semantic_loop.py `
    --data-pack .tmp\adventureworks-semantic `
    --review-batch public-benchmark-fixture

.\.venv\Scripts\python scripts\run_db_runtime_query_smoke.py `
    --data-pack .tmp\adventureworks-semantic `
    --max-plans 5

.\.venv\Scripts\python scripts\build_semantic_asset_feedback.py `
    --data-pack .tmp\adventureworks-semantic

.\.venv\Scripts\python scripts\build_offline_acceptance_report.py `
    --data-pack .tmp\adventureworks-semantic
```

The DB runtime smoke seeds a temporary in-memory SQLite database plus a
temporary dataset-storage copy, then calls the existing runtime query service.
It reads bounded rows and creates runtime audit records, but it does not write
the application database, publish packages, activate runtime, or create real
governance issues.

To produce accepted changes, create
`.tmp\adventureworks-semantic\governance_review_decisions.json` with reviewed
decisions such as:

```json
{
  "decision_version": "1.0",
  "review_batch": "pilot-review",
  "decisions": [
    {
      "review_item_id": "gov-0001",
      "decision": "accept",
      "reviewer": "ontology_steward",
      "reviewed_at": "2026-07-09T08:00:00+00:00",
      "rationale": "Accepted for offline draft generation."
    }
  ]
}
```

Accepted ontology drafts are still offline artifacts. They preserve reviewed
evidence and rationale for the next package bridge, but they do not write to
the database, apply model changes, publish a package, or become runtime facts.
The offline model package bridge writes a stable semantic hash only when
accepted drafts exist; with no accepted drafts it reports `NO_ACCEPTED_DRAFTS`.
The offline dataset binding bridge binds a built package to manifest and
mapping-contract table metadata; when there is no built package it reports
`NO_BINDABLE_PACKAGE` and keeps runtime activation out of scope.
The offline runtime query dry run emits explain-only query plans for bindable
datasets; when binding is not ready it reports `NO_RUNTIME_QUERY_READY` and
does not read rows, execute runtime queries, or create audit records.
The semantic asset feedback loop converts review, package, binding, and query
readiness gaps into an offline backlog artifact. It does not write the
database or create real governance issues.
The offline acceptance report summarizes the whole chain and names the current
gate, such as `BLOCKED_BY_HUMAN_REVIEW` when review decisions are still
missing.

To inspect each step separately, run the offline ontology operationalization chain:

```powershell
# 1. Generate the manufacturing data pack
.\.venv\Scripts\python scripts\generate_manufacturing_dataset.py `
    --preset tiny --output-dir .tmp\phase19-manufacturing

# 2. Validate the data pack contract
.\.venv\Scripts\python scripts\validate_manufacturing_data_pack.py `
    .tmp\phase19-manufacturing

# 3. Generate field-to-business-property mappings
.\.venv\Scripts\python scripts\generate_mapping_contract.py `
    --data-pack .tmp\phase19-manufacturing

# 4. Validate the mapping contract
.\.venv\Scripts\python scripts\validate_mapping_contract.py `
    --data-pack .tmp\phase19-manufacturing

# 5. Run deterministic business rule validation
.\.venv\Scripts\python scripts\validate_business_rules.py `
    --data-pack .tmp\phase19-manufacturing

# 6. Generate human-reviewable governance feedback
.\.venv\Scripts\python scripts\generate_governance_feedback.py `
    --data-pack .tmp\phase19-manufacturing
```

Phase 19 closeout verified:

| Artifact | Purpose |
|----------|---------|
| `manifest.json` | 13 tables, PK/FK, row counts, core pilot subset, business meaning |
| `mapping_contract.json` | 13 object types, 15 relationships, controlled value/role/null vocabularies |
| `rule_validation_report.json` | 8 rule categories, deterministic checks, bounded findings |
| `governance_feedback.json` | Human-reviewable governance candidates by type and severity |
| FDE artifact markdown | Bounded business delivery artifact with quality gate |

## Architecture Chain

```text
Auth + group isolation
-> document ingestion
-> hybrid retrieval
-> citation-grounded RAG
-> user-confirmed task/action
-> controlled Agent/HITL workflow
-> ontology governance
-> modeling drafts
-> quality-gated packages
-> business contracts
-> dataset bindings
-> runtime query
-> relationship traversal (1-2 hop, bidirectional, sortable)
-> outcome artifacts
-> governance feedback
```

The implementation intentionally favors explainable backend boundaries over broad framework adoption.

## Key Capabilities

- JWT auth, BCrypt password hashing, refresh-token rotation, group RBAC.
- Hard `group_id` isolation across documents, chunks, retrieval, RAG, tasks, Agent runs, ontology entities, model packages, projects, datasets, bindings, outcomes, and evidence links.
- Document ingestion for Markdown, TXT, PDF, and DOCX.
- Keyword + semantic retrieval with PostgreSQL/pgvector support.
- Citation-grounded RAG with confidence, knowledge gaps, next steps, and persisted audit records.
- Controlled Agent orchestration with tool registry, HITL confirmation, and audit trail.
- Ontology governance: entities, relations, validation issues, curation, modeling drafts.
- Quality-gated immutable ontology model packages.
- Business pilot workflow: Goal -> Data -> Model -> Validate -> Pilot.
- Dataset profiling, deterministic modeling draft generation, explicit dataset bindings.
- FDE outcome records, outcome summaries, and bounded markdown artifacts.
- Relationship runtime traversal: 1-2 hop hash joins via `POST /runtime/traverse`, per-OT field whitelist, filters on any OT, bidirectional (forward/reverse), grouped/flat response shapes, stable multi-key sorting, explain-only mode, fail-closed audit, FK-indexing optimizations. 122 tests. No SQL, no DSL, no Graph RAG. Aggregation deferred.
- Phase 19 offline data-governance chain: data pack -> mapping -> rules -> governance feedback.

## Intentional Boundaries

These are deliberate design boundaries, not missing checkboxes:

- **No MCP runtime.** MCP remains a future Agent-facing adapter candidate. Design doc only.
- **No Graph RAG.** The project has ontology entities/relations, but retrieval is still hybrid search.
- **No R3E2 aggregation.** COUNT/SUM/AVG deferred indefinitely - crosses from "traversal" into "analytics query" DSL territory.
- **No autonomous Agent writes.** High-risk write behavior requires backend permission checks and human confirmation.
- **No private enterprise data.** The manufacturing data pack is realistic synthetic data.
- **AdventureWorks remains an offline benchmark path.** `scripts/export_adventureworks.py`
  exports the focused raw CSV + manifest pack, and
  `scripts/map_adventureworks_to_semantic_pack.py` maps it into the full
  Semantic CI contract. It does not write the app database or change runtime
  behavior.
- **No DB-backed governance feedback yet.** Phase 19 produces offline candidates only.
- **No Neo4j, OWL reasoner, LangGraph, OSDK, or Kubernetes dependency in the core runtime.**

## Local Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
pip install -e .
docker compose up -d postgres
alembic upgrade head
uvicorn semantic_lighthouse.main:app --reload
```

Open API docs:

```text
http://127.0.0.1:8000/docs
```

SQLite smoke mode is available for local scripts and tests; most demo scripts create their own temporary database.

## Verification

Use targeted checks instead of defaulting to full regression:

```powershell
# Phase 19 related tests
.\.venv\Scripts\python -m pytest `
    tests\test_manufacturing_data_pack.py `
    tests\test_business_rule_validation.py `
    tests\test_governance_feedback.py `
    -p no:cacheprovider

# FDE smoke
.\.venv\Scripts\python scripts\smoke_fde_demo.py `
    --data-pack .tmp\phase19-manufacturing

# Documentation alignment
.\.venv\Scripts\python scripts\check_doc_alignment.py
```

Full backend regression and UI smoke are lane-dependent. See `docs/development-workflow.md`.

## Key Documents

| Document | Purpose |
|----------|---------|
| `PRODUCT.md` | Product positioning and boundaries |
| `docs/project-status.toml` | Canonical current project state |
| `docs/project-roadmap.md` | Current decision roadmap |
| `docs/mac-development-migration.md` | Windows-to-Mac development migration |
| `docs/deployment-v3-cloud.md` | Cloud deployment guide |
| `docs/CODEMAPS/` | Architecture, backend, data, and frontend structure snapshots |

## Public Repository Boundary

This is a personal project showcase repository. Please note:

- **No real production configuration.** `.env.production` is not committed. All example files use placeholder values.
- **No real API keys or secrets.** `.env.example` has empty key fields. Production safety checks enforce non-default secrets at runtime (`config.py:validate_runtime_safety()`).
- **No private knowledge base.** The default `knowledge_base_path` is `./knowledge-graph` (a local directory you create yourself). The external knowledge base referenced in some demo scripts is not included.
- **Deployment docs are reference guides**, not snapshots of any real server. They describe a generic Ubuntu deployment flow.

## Current Status

Canonical project state: `docs/project-status.toml`.

### Delivered

| Line | Scope | Status |
|------|-------|--------|
| Phase 1-18 | Auth, ingestion, retrieval, RAG, Agent, ontology governance, modeling, contracts, pilot workflow, outcomes, deployment smoke, frontend baseline | Complete |
| Phase 19 | Offline ontology operationalization (CSV -> manifest -> mapping -> rules -> governance feedback) | Complete |
| R2 | Relationship runtime traversal foundation (1-2 hop, API, audit) | Complete |
| R3A-R3F | Runtime enhancements: grouped response, filter pushdown, bidirectional traversal, sorting, FK indexing | Complete |

### Deferred

| Item | Reason |
|------|--------|
| R3E2 aggregation (COUNT/SUM/AVG) | Crosses DSL boundary; needs measured demand |
| MCP runtime | Future candidate; design doc only |
| Graph RAG | Deferred until entity/relation read model is reliable |
| AdventureWorks benchmark | Raw export adapter and Semantic CI mapping adapter exist |
| DB-backed governance feedback | Safety Lane candidate; offline candidates exist |

### Next Step Candidates

The project is at a decision gate. No automatic expansion to new phases. Candidates require explicit user choice:

1. **Semantic CI/CD productization** - turn mapping, rules, evidence, and governance feedback into a repeatable delivery discipline.
2. **HITL evidence packet** - show evidence, affected objects, risk, and rollback notes before confirmed writes.
3. **Strong/weak relation governance** - distinguish contractual relations from inferred or weak relations.
4. **AdventureWorks benchmark** - compare real benchmark governance findings against the synthetic manufacturing pack.
5. **Metric-to-ontology mapping MVP** - connect KPIs to ontology objects, properties, evidence, and lineage without opening a broad analytics DSL.
