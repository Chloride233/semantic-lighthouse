# Semantic Lighthouse — Portfolio Demo Narrative

**Date**: 2026-06-22
**Purpose**: Explain what Semantic Lighthouse is, what it proves, and why it
matters — for portfolio review, interview preparation, and technical
demonstration.

---

## One-Paragraph Elevator Pitch

Semantic Lighthouse is an **Ontology semantic operating layer workspace**
built for enterprise AI transformation. It proves that enterprise AI is not
just about calling LLMs — it's about building a trustable chain from
permission-aware document ingestion through citation-grounded answers to
auditable business outcomes. The project evolves from trusted RAG into a
complete Ontology pipeline: business objects, properties, relationships,
actions, permissions, evidence, and Agent-facing interfaces. Every step is
explainable in business terms, technical terms, risk terms, and interview
terms.

## What This Project Is (And Isn't)

| Is | Is Not |
|----|--------|
| An Ontology semantic operating layer workspace | A generic RAG chatbot |
| A controlled Agent coordination layer | An autonomous Agent platform |
| A full-stack enterprise AI engineering demo | A productized SaaS |
| A permission-aware, audit-friendly system | A framework playground |
| Built with FastAPI + PostgreSQL + vanilla JS | Built with heavy frontend frameworks |
| Explainable in business AND technical terms | A black-box LLM wrapper |

## The Journey: Phase 8 → Phase 19

Semantic Lighthouse progressed through 12 major phases, each proving a
specific engineering capability:

### Foundation (Phases 8–10): RAG → Agent → Ontology Governance

- **Phase 8**: Experience integration — RAG → user-confirmed task →
  Agent/HITL → audit. Demonstrable loop with real KB.
- **Phase 9**: Ontology Core v1 — 74 real docs → 74 entities, 186 relations,
  97 governance issues. Proved the KB is governable.
- **Phase 10**: Governance Operations — issue triage, curation workflow,
  evidence-to-ontology bridge. 97 issues → 39 curated backlog entries.

### Modeling & Quality (Phases 11–13): Drafts → Packages → Contracts

- **Phase 11**: Ontology Modeling Drafts v1 — human-reviewable draft
  lifecycle with evidence refs.
- **Phase 12**: Model Quality & Contract Packages — quality-gated immutable
  packages with semantic hashing.
- **Phase 13**: Typed Business Ontology Contract & Manufacturing Pilot —
  business_v1 contract profile, 11-draft manufacturing pilot.

### Business Pilot (Phases 14–16): Projects → Evidence → Outcomes

- **Phase 14**: Business Pilot Project — five-stage chain: Goal → Data →
  Model → Validate → Pilot. Full frontend (F2) delivered with vanilla JS.
- **Phase 15**: Evidence-to-Ontology Feedback — RAG answers as project
  evidence, evidence review surface, evidence-backed draft proposals.
- **Phase 16**: Pilot Outcome & FDE Delivery — immutable outcome records,
  JSON outcome-summary aggregation, bounded markdown artifact export with
  quality gate. 66 tests.

### Demo Readiness (Phase 17): Smoke → Contract → Validation

- **Phase 17**: FDE Demo Readiness — manufacturing seed scenario, 11-step
  smoke script (~0.8s, zero external dependencies), inline artifact quality
  gate (7 required sections, 11 forbidden terms, 5 boundedness rules).
  Interview script with 5-minute demo flow.

### Cloud & Visual (Phase 18): Deployment → Polish

- **Phase 18**: Cloud Deployment Smoke — PostgreSQL migration (28/28),
  HTTP API smoke (9/9 PASS), base-url adapter, config audit (11 items).
  Frontend visual baseline refresh with Minimalism & Swiss Style.

### Ontology Operationalization (Phase 19): Data → Rules → Governance

- **Phase 19.1**: Manufacturing Data Pack Contract — manifest.json with
  13 tables, PK/FK/row_count/core_pilot/business_meaning.
- **Phase 19.2**: FDE Smoke Reads Data Pack — smoke script accepts
  `--data-pack`, validates manifest, prints summary.
- **Phase 19.3**: Mapping Contract v1 — 13 object types, 15 relationships,
  deterministic column-to-property mappings with controlled vocabularies.
- **Phase 19.4**: Rule Validation v1 — 8 rule categories, 4,528 checks,
  offline rule_validation_report.json.
- **Phase 19.5**: Governance Feedback v1 — rule findings → 103
  human-reviewable governance candidates (3 types, 4 severity levels).
- **Phase 19.6**: Closeout — full pipeline verification, 29 tests, 5
  offline artifact types. Phase 19 complete.

## The Architecture: What Makes It Different

### 1. Permission-Aware From Day One

Every API endpoint enforces `group_id` isolation at the database query
level. JWT access tokens (15min) + httpOnly refresh cookies with rotation
and replay detection. BCrypt passwords. Three role levels per group
(Owner/Admin/Member). This is not bolted on — it's the foundation.

### 2. Citation-Grounded RAG, Not "Ask and Hope"

Every RAG answer carries: retrieved citations with source paths, confidence
reasoning, identified knowledge gaps, and suggested next steps. The local
evidence gate refuses to call the LLM if no citations were retrieved.
Answers are auditable through persisted RAG run records.

### 3. Controlled Agent, Not Autonomous Agent

Agent is a coordination layer for multi-step, multi-tool workflows that
need audit trails. Deterministic backend logic (permissions, status filters,
hash checks, CRUD) is never replaced by LLM decisions. All Agent write
actions require role authorization, group_id isolation, and user
confirmation (HITL).

### 4. Ontology Governance, Not Just "More RAG"

The project goes beyond retrieval. Phases 9–19 prove:
- Entity extraction from real documents with wikilink relations
- Governance issue detection and curation workflows
- Human-reviewed modeling drafts with evidence references
- Quality-gated immutable packages with semantic hashing
- Business contracts with typed properties and relationships
- Offline data pack contracts with PK/FK/row_count validation
- Deterministic mapping contracts with controlled vocabularies
- Business rule validation (8 categories, 4,528 checks)
- Governance feedback candidates (3 types, 4 severity levels)

### 5. Engineering Discipline

- **Zero npm dependencies** on the frontend — vanilla JS ES modules + hash router
- **Stdlib-only data pipeline** — no pandas, no Spark, no external CSV libraries
- **Fake providers** enable zero-dependency smoke tests
- **Temporary SQLite** enables in-process integration testing
- **29 tests** across 3 test files for the data pipeline alone
- **Ruff** for linting, **pytest** for testing, **Alembic** for migrations
- **Boundary discipline**: what's NOT built is as important as what IS built

## The Demo: 11 Steps in Under 1 Second

```powershell
.\.venv\Scripts\python scripts\smoke_fde_demo.py \
    --data-pack .tmp\phase19-manufacturing
```

Produces:

```text
Data pack: provided: .tmp\phase19-manufacturing
  manifest_version: 1.0
  data_pack:        manufacturing
  preset/seed:      tiny / seed=42
  table_count:      13
  core_pilot_count: 8
  total_rows:       279

  [PASS] register
  [PASS] login
  [PASS] create_group
  [PASS] create_project
  [PASS] seed_evidence
  [PASS] seed_package
  [PASS] seed_runtime
  [PASS] create_outcome
  [PASS] outcome_summary
  [PASS] outcome_artifact
  [PASS] artifact_quality_gate — PASS (0 findings)

FDE Demo Smoke: PASS — 11/11 — 0.7s
Artifact gate: PASS
```

The full chain proven in that sub-second run:

```text
manufacturing CSV → manifest.json → mapping_contract.json
→ rule_validation_report.json → governance_feedback.json
→ registration → login → group → project → evidence → package
→ runtime → outcome → markdown artifact → quality gate
```

## What A Reviewer Should Take Away

1. **This is not a "RAG demo."** It's a semantic operating layer with a
   governed ontology pipeline that goes from raw data to human-reviewable
   governance candidates.

2. **The engineering is real.** Permission isolation, audit trails,
   deterministic validation, bounded artifacts — these are enterprise-grade
   patterns, not tutorial code.

3. **The scope is intentional.** MCP, Neo4j, OWL, LangGraph, Kubernetes —
   all intentionally deferred. The project proves depth over breadth.

4. **The narrative is coherent.** Every phase builds on the previous one.
   The progression from "can we RAG?" to "can we govern an ontology?" is
   traceable through commits, tests, and documentation.

5. **The demo is reproducible.** `smoke_fde_demo.py` runs in under a second
   with zero external dependencies. No API keys, no cloud services, no
   Docker needed.

## Entry Points For Different Audiences

| Audience | Start Here |
|----------|-----------|
| Technical reviewer | `README.md` → `docs/portfolio-demo-narrative.md` (this file) |
| Architecture reviewer | `AGENTS.md` → `docs/phase19-architecture-tech-selection-judgment.md` |
| Product/business reviewer | `PRODUCT.md` → `docs/product-alignment-prd.md` |
| Interviewer (5-min demo) | `docs/interview-demo-questions.md` |
| Developer continuing work | `CLAUDE.md` → `docs/agent-handoff.md` |
| Project state check | `docs/project-status.toml` |

## Key Documents Index

| Document | Purpose |
|----------|---------|
| `README.md` | Public-facing project overview |
| `PRODUCT.md` | Product brief and capability summary |
| `docs/portfolio-demo-narrative.md` | This file — portfolio narrative |
| `docs/project-status.toml` | Canonical project state (single source of truth) |
| `docs/agent-handoff.md` | Operational context for next session |
| `docs/phase19-planning.md` | Phase 19 slice plan and delivery record |
| `docs/phase19-architecture-tech-selection-judgment.md` | Architecture and technology decisions |
| `docs/adventureworks-benchmark-planning.md` | External benchmark candidate evaluation |
| `docs/interview-demo-questions.md` | 5-minute demo script and FAQ |
| `docs/product-alignment-prd.md` | Product requirements and alignment |
| `docs/project-roadmap.md` | Historical roadmap |
| `docs/development-workflow.md` | Lane system and verification rules |
