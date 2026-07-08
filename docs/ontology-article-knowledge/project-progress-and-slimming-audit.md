---
title: Project Progress And Slimming Audit
tags:
  - semantic-lighthouse/audit
  - ontology/articles
  - slimming
created: 2026-07-08
status: draft
---

# Project Progress And Slimming Audit

This audit saves the post-knowledge-base project review and adds a slimming-oriented review against the principles distilled in [[synthesis]] and [[semantic-lighthouse-fit]].

## Audit Basis

- Project status: `docs/project-status.toml`
- Product identity: `PRODUCT.md`
- Product boundary: `docs/product-alignment-prd.md`
- Roadmap: `docs/project-roadmap.md`
- Knowledge synthesis: `docs/ontology-article-knowledge/synthesis.md`
- Project fit note: `docs/ontology-article-knowledge/semantic-lighthouse-fit.md`

## Current Progress Assessment

Semantic Lighthouse is past the generic RAG demo stage. The project has already reached an ontology-oriented semantic operating layer prototype:

- Auth, role permissions, refresh-token rotation, and group isolation are stable.
- Document ingestion, ETL, keyword/semantic/hybrid retrieval, citation-ready chunks, and RAG run audit exist.
- RAG answers expose citations, confidence, gaps, next steps, and task handoff.
- Controlled Agent orchestration exists with HITL and audit boundaries.
- Ontology governance, entities, relations, validation issues, graph/detail views, draft generation, draft review, model quality gates, immutable packages, business contracts, and Pilot runtime are implemented.
- Phase 19 delivered a full offline semantic governance loop: CSV -> manifest -> mapping contract -> business rule validation -> governance feedback.
- R2/R3 relationship runtime delivers 1-2 hop traversal, grouped/flat response, filter pushdown, bidirectional traversal, sorting, audit, and FK indexing.

The project is strongest where it follows the article corpus:

- It treats ontology as business objects, relationships, actions, permissions, evidence, and interfaces, not as a decorative graph.
- It keeps Agent behavior controlled, audited, and confirmation-gated.
- It prefers deterministic backend rules over LLM decisions.
- It has an early Semantic CI/CD shape in Phase 19.

## Current Gaps Against Knowledge-Base Principles

### G1. Semantic CI/CD Is Still Mostly Offline

Phase 19 is a good offline chain, but it is not yet a productized semantic lifecycle. Missing pieces:

- DB-backed review queue for governance candidates.
- Evidence packet UI for each candidate.
- Versioned merge/release of accepted semantic assets.
- Runtime feedback loop from failed mappings, rejected proposals, and semantic todos.

Principle reference: A18, A42, A48 in [[source-index]].

### G2. Semantic Asset Base Is Incomplete

The current product has ontology, contracts, mapping, validation, and governance feedback. It does not yet have a first-class metrics system or metric-ontology mapping layer.

Missing pieces:

- Metric definitions with owner, formula, dimensions, source, refresh cadence, and version.
- Mapping between metric dimensions and ontology entities.
- Handoff protocol between Data Agent reasoning and Ontology Agent reasoning.

Principle reference: A22, A37, A38, A42.

### G3. HITL Needs Evidence-Packet Discipline

The project has confirmation and audit, but review surfaces should avoid becoming generic approve/reject buttons.

Needed for future review flows:

- Source data and source document anchors.
- Rule or constraint that triggered the proposal.
- Severity/risk class and confidence.
- Proposed action and blast radius.
- Rejection/escalation reason.

Principle reference: A02, A05, A10, A14, A20.

### G4. Strong/Weak Relation Split Is Not Yet Explicit Enough

The current model distinguishes drafts, packages, runtime traversal, and governance feedback, but the product vocabulary does not yet consistently separate:

- Approved hard relationships.
- Candidate relationships.
- Weak signals from embeddings, co-occurrence, LLM extraction, or similarity.

This matters before any LLM-based relation extraction or weak-signal graph expansion.

Principle reference: A47.

### G5. External Benchmark Is Planned, Not Landed

AdventureWorks is planned as an external benchmark, but not implemented. The current manufacturing data pack is realistic synthetic data, which is useful for demos but weaker as proof of generalization.

Principle reference: A27 and A45: small scenes are valid when they compound and when cost/effort produces reusable semantic assets.

### G6. Product Narrative Has Some Stale or Diffuse Entry Points

The core story is strong, but a reviewer can still get distracted by:

- A long accumulated roadmap.
- Repeated out-of-scope sections.
- Stale CODEMAPS that do not match current frontend routes and router count.
- Multiple historical demo scripts and planned/deferred artifacts.

Principle reference: A01/A19/A27/A36: avoid demo-only or non-compounding artifacts; every artifact should deposit reusable value.

## Slimming Audit

The repository does not appear to track hard generated garbage such as `__pycache__`, `.pyc`, `.egg-info`, `.tmp`, runtime storage, databases, or logs. Local `.pyc` files exist but are ignored and not tracked.

The main slimming opportunity is narrative and artifact consolidation.

### Priority 1: Documentation Slimming

#### S1. Condense `docs/project-roadmap.md`

Current issue:

- It is the largest doc file.
- It contains many complete historical phases, repeated out-of-scope lists, deferred notes, and old next-step statements.
- It competes with `docs/project-status.toml` as the mental source of truth even though status should be canonical.

Recommended action:

- Keep a short active roadmap focused on current baseline, decision gate, and next candidates.
- Move historical phase details into `docs/archive/roadmap-history.md` or remove redundant detail after confirming no unique acceptance criteria are needed.

Risk:

- Low if `project-status.toml`, README, and phase-specific docs retain the current state.

#### S2. Refresh or Remove `docs/CODEMAPS/*`

Current issue:

- CODEMAPS were generated around the earlier R1 frontend and show outdated router/service counts.
- `docs/CODEMAPS/frontend.md` lists old primary nav and omits current Pilot/Ontology routes.

Recommended action:

- Either regenerate CODEMAPS after F2/R3 or remove them if they are not actively maintained.
- If kept, add "generated snapshot" status and date clearly.

Risk:

- Medium-low. Stale maps are more harmful than absent maps for architecture review.

#### S3. Merge Repeated Boundary Language

Current issue:

- MCP, Graph RAG, LangGraph, OWL, Neo4j, OSDK, Kubernetes, and Agent auto-write boundaries are repeated across README, PRODUCT, PRD, roadmap, phase docs, and MCP design.

Recommended action:

- Keep canonical boundary language in `docs/product-alignment-prd.md` and `docs/project-status.toml`.
- Let README summarize with links.
- Archive or reduce repeated lists in older phase sections.

Risk:

- Low, as long as the canonical boundary remains obvious.

### Priority 2: Demo/Script Slimming

#### S4. Classify Historical Demo Scripts

Current candidates:

- `scripts/run_ontology_governance_demo.py`
- `scripts/run_ontology_curation_demo.py`
- `scripts/run_ontology_modeling_demo.py`
- `scripts/run_ontology_model_package_demo.py`

Current issue:

- These scripts represent historical phase demos. Some generate reports that are not currently tracked.
- They may be valuable as regression helpers, but they add conceptual load.

Recommended action:

- Add a small `scripts/README.md` that classifies scripts as current smoke, current Phase 19 pipeline, historical demo, deployment, or development helper.
- After classification, consider moving historical phase demo scripts into `scripts/archive/` if no tests import them.

Known constraint:

- `tests/test_ontology_modeling_demo.py` imports `scripts/run_ontology_modeling_demo.py`, so do not move/delete it without updating tests.

Risk:

- Medium if tests or demo docs still reference them.

#### S5. Review `scripts/download_ecommerce_datasets.py`

Current issue:

- Ecommerce dataset downloading appears outside the current ontology manufacturing/pilot semantic operating layer narrative.
- External dataset downloading can distract from the current AdventureWorks benchmark direction.

Recommended action:

- If unused, archive or remove it.
- If retained, mark as research-only and not part of current demo.

Risk:

- Low if no tests or docs rely on it.

#### S6. Review Screenshot Scripts

Current candidates:

- `scripts/screenshots_f2b.py`
- `scripts/screenshots_legacy_polish.py`

Current issue:

- Useful for visual QA, but could be treated as dev tools rather than product assets.

Recommended action:

- Keep if still used for UI baselines.
- Otherwise archive with visual baseline artifacts.

Risk:

- Low to medium depending on UI verification workflow.

### Priority 3: Frontend Slimming

#### S7. Review `static/learning.html`

Current issue:

- `static/learning.html` appears unreferenced except by itself.
- It is outside the current `/console` SPA route map.

Recommended action:

- Remove or archive if it is not intentionally exposed as a standalone learning artifact.

Risk:

- Low if no user-facing link exists.

#### S8. Preserve Legacy Console Routes Until Explicitly Retired

Current issue:

- `jobs.js`, `rag.js`, and other legacy routes are still registered.
- AGENTS.md explicitly says legacy console routes should remain working unless retirement is scoped.

Recommended action:

- Do not delete legacy routes in a casual cleanup.
- If slimming frontend, create an explicit retirement task with route inventory, screenshots, and redirect plan.

Risk:

- Medium because removing these can break smoke/demo expectations.

### Priority 4: Status Hygiene

#### S9. Update `project-status.toml` Latest Commit

Current issue:

- `latest_commit` still points to `f4bccfb`; the knowledge-base commit is `7d00c62`.

Recommended action:

- Update only during a status/doc hygiene slice.

Risk:

- Low.

#### S10. Align README Next Candidates With Knowledge-Base Audit

Current issue:

- README's next candidates predate this article-driven audit.

Recommended action:

- Replace or supplement with:
  - Semantic CI/CD productization.
  - HITL evidence packet.
  - Strong/weak relation governance.
  - AdventureWorks benchmark.
  - Metric-ontology mapping MVP.

Risk:

- Low.

## What Not To Slim Yet

Do not slim these without a dedicated implementation review:

- `src/semantic_lighthouse/services/runtime_*`: core R2/R3 runtime.
- `src/semantic_lighthouse/services/ontology_*`: core ontology chain.
- Alembic migrations: historical schema chain must remain intact.
- Tests around permissions, group isolation, runtime audit, ontology packages, and traversal.
- `docs/mcp-agent-boundary-design.md`: still valuable as a boundary document, even though runtime MCP is absent.
- `docs/adventureworks-benchmark-planning.md`: useful next benchmark candidate.
- Legacy console routes: retire only with explicit scoped task.

## Recommended Slimming Order

1. Save this audit. Done in this file.
2. Documentation pass:
   - Condense roadmap.
   - Refresh or remove CODEMAPS.
   - Deduplicate boundary language.
3. Script inventory pass:
   - Add `scripts/README.md`.
   - Mark current vs historical scripts.
   - Move only unused historical scripts after checking tests and docs.
4. Frontend standalone artifact pass:
   - Decide fate of `static/learning.html`.
   - Leave legacy SPA routes intact unless explicitly retiring.
5. Status hygiene:
   - Update latest commit and next candidates after slimming decisions.

## Proposed First Slimming Slice

Fast Lane, documentation only:

- Create `docs/archive/`.
- Replace `docs/project-roadmap.md` with a concise active roadmap.
- Move old phase-by-phase history into `docs/archive/project-roadmap-history.md`.
- Update README next candidates to match the article-driven audit.
- Run `git diff --check`, `git status --short`, and `scripts/check_doc_alignment.py`.

This gives the biggest reduction in reviewer confusion without touching runtime code.
