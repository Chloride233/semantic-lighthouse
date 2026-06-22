# Semantic Lighthouse / 语义灯塔

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

Run the offline ontology operationalization chain:

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
- Phase 19 offline data-governance chain: data pack -> mapping -> rules -> governance feedback.

## Intentional Boundaries

These are deliberate design boundaries, not missing checkboxes:

- No MCP runtime yet. MCP remains a future Agent-facing adapter candidate.
- No Graph RAG yet. The project has ontology entities/relations, but retrieval is still hybrid search.
- No autonomous Agent writes. High-risk write behavior requires backend permission checks and human confirmation.
- No real enterprise data. The manufacturing data pack is realistic synthetic data.
- No AdventureWorks implementation yet. It is planned as a future external benchmark.
- No DB-backed governance feedback yet. Phase 19 produces offline candidates only.
- No Neo4j, OWL reasoner, LangGraph, OSDK, or Kubernetes dependency in the core runtime.

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

## Portfolio And Interview Docs

| Document | Purpose |
|----------|---------|
| `docs/portfolio-demo-narrative.md` | Portfolio-level project story and demo narrative |
| `docs/interview-demo-questions.md` | Interview demo script and FAQ |
| `docs/project-status.toml` | Canonical current project state |
| `docs/agent-handoff.md` | Operational handoff for future sessions |
| `docs/phase19-planning.md` | Phase 19 delivery record |
| `docs/adventureworks-benchmark-planning.md` | Future external benchmark plan |
| `docs/phase19-architecture-tech-selection-judgment.md` | Architecture and technology selection rationale |
| `PRODUCT.md` | Product positioning and boundaries |

## Current Status

Current canonical status lives in:

```text
docs/project-status.toml
```

As of Phase 19 closeout, the project has delivered the full offline ontology operationalization chain and portfolio narrative. Recommended next options:

1. Public demo video / screenshot package.
2. AdventureWorks external benchmark implementation planning.
3. Safety Lane for DB-backed governance feedback from confirmed candidates.
