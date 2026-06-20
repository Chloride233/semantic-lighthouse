# Product Rationalization and Surface Consolidation Review

Date: 2026-06-20
Status: S2.1 contextual guidance delivered. S2.2 project evidence contract design pending approval.

## 1. FDE Role and Main Chain

**FDE** means **Forward Deployed Engineer** — the role that bridges business problems to product capabilities. The FDE workflow is:

```
业务问题定义 → 接入数据/知识 → Ontology 建模 → 与业务用户验证 → Pilot 落地 → 衡量并迭代
(business problem → data/knowledge access → Ontology modeling → validation with business users → Pilot landing → measure & iterate)
```

The **Phase 14 Guided Pilot five-stage flow** is the current product main chain implementing the middle of this workflow:

```
目标 (goal) → 数据 (data) → 模型 (model) → 验证 (validate) → Pilot (pilot)
```

The Pilot five stages are the product's primary user path but do NOT represent the full scope of FDE responsibilities. FDE also involves problem framing, evidence gathering, stakeholder communication, and iteration measurement — activities that extend beyond the product UI.

**Primary user path**: Login → Workspace → Pilot list → Create project → Upload CSV/XLSX → Generate model drafts → Batch review → Build package → Generate bindings → Activate → Query runtime

**Pilot 5-stage backend routers** (4): `projects.py`, `datasets.py`, `ontology.py` (main + project_model_router), `runtime.py`

**Pilot 5-stage frontend pages** (6): `project.js`, `project-model.js`, `project-validate.js`, `project-pilot.js`, `project-dialog.js`, `projects.js`

**Mandatory infrastructure** (2 routers): `auth.py`, `groups.py`

**Evidence support services** — useful for the FDE role to access knowledge/evidence, but not a hard dependency of the dataset-only Pilot path: `embeddings.py`, `chat.py`, `retrieval.py`. These services provide value when the FDE needs to ground business problems in existing enterprise knowledge, but the Pilot five-stage chain functions without them for dataset-driven projects.

**Ontology governance pipeline** (feeds model stage and is the product's north star capability): `ontology.py` service, `ontology_drafts.py`, `ontology_draft_reviews.py`, `ontology_draft_quality.py`, `ontology_packages.py`, `business_contract_validator.py`, `business_contract_compiler.py`

---

## 2. Classification Table

### KEEP — Essential to FDE main chain

| # | Capability | Layer | Files | Rationale |
|---|-----------|-------|-------|-----------|
| K1 | Pilot 5-stage flow | Backend + Frontend | 4 routers, 11 services, 6 frontend pages | Core product value — the FDE main chain |
| K2 | Auth + Groups | Backend | `auth.py`, `groups.py` routers | Mandatory infrastructure for any user flow |
| K3 | Ontology governance | Backend | `ontology.py` router, 7 ontology services | Feeds model stage with drafts, quality gates, packages, contracts |
| K4 | Embedding + Chat + Retrieval | Backend | `embeddings.py`, `chat.py`, `retrieval.py` | Needed by RAG (evidence feeds Pilot goal) and Conversations |
| K5 | Document management | Backend + Frontend | `documents.py` router, 5 document services, `documents.js` | Knowledge base ingestion — evidence for RAG |
| K6 | Navigation shell | Frontend | `navbar.js`, `app.js`, `router.js`, `state.js`, `api.js` | Application infrastructure |
| K7 | Project status + doc checker | Scripts + Docs | `project-status.toml`, `check_doc_alignment.py`, `development-workflow.md` | Product governance — prevents doc drift |
| K8 | All database models | Backend | `models.py` (27 models), 23 migrations | Data integrity — migrations are never deleted |
| K9 | All pytest tests | Tests | `tests/` (749 tests) | Verification — regression protection |
| K10 | verify_ui + screenshots | Scripts | `verify_ui.py`, `screenshots_f2b.py` | UI verification |
| K11 | Demo scripts | Scripts | 5 ontology/manufacturing demo scripts | Portfolio evidence — reproducible phase demos |
| K12 | Deployment scripts | Scripts | `scripts/docker/start-api.sh`, `bootstrap-ubuntu.sh`, `smoke-cloud.sh`, `start_local_app.ps1`, `start_local_preview.ps1`, `start/stop-v1-api.ps1` | Operations |
| K13 | Eval harness | Scripts | `evaluate.py`, `run_eval.py`, `check_eval_thresholds.py`, `run_rag_quality_eval.py` | Retrieval quality measurement |
| K14 | Product definition docs | Docs | `PRODUCT.md`, `product-alignment-prd.md`, `agent-handoff.md`, `project-roadmap.md`, `interview-demo-questions.md` | Product narrative |
| K15 | Engineering memory | Docs | `highlight-log.md`, `pitfall-log.md`, `learning-index.md` | Ongoing learning |

### CONSOLIDATE — Valuable; surface integration candidate for S2

| # | Capability | Current State | S2 Consideration |
|---|-----------|---------------|-----------------|
| C1 | Tasks (轻量任务) | Independent page at `/tasks`, in "更多工具" dropdown | Pilot "Actions" tab — confirmed next steps appear here |
| C2 | RAG Answer (知识问答) | Independent page at `/ask`, in "更多工具" dropdown | Pilot "Ask" tab in goal stage — knowledge exploration before project creation |
| C3 | Conversations (多轮对话) | Independent page at `/conversations`, in "更多工具" dropdown | Fold into Pilot "Ask" tab as session history |
| C4 | Agent console | Independent page at `/agent`, in "更多工具" dropdown | Pilot "Advanced" tab — only visible for complex multi-step workflows |
| C5 | Ontology standalone workspace | Independent page at `/ontology`, in primary nav | Whether to integrate into Pilot or keep as standalone workspace — S2 decision. Ontology is the product north star; its navigation placement requires careful evaluation. |

### HIDE — Keep backend and frontend pages; S2 navigation evaluation

| # | Capability | Current Visibility | S2 Consideration |
|---|-----------|-------------------|-----------------|
| H1 | ETL Jobs page | Already hidden (no nav entry) | Keep for operator troubleshooting |
| H2 | RAG Debug console | Already hidden (no nav entry) | Keep for developer debugging |
| H3 | "更多工具" dropdown | Currently 5 entries | S2: evaluate reducing to 3 after C2/C3/C4 surface consolidation is proven. S1: do not hide any entries. |

**Note**: Ask, Conversations, and Agent remain in "更多工具" during S1. They are not hidden until S2 validates that the Pilot surface consolidation is complete and functional. Premature hiding would break existing user workflows with no replacement.

### REMOVE — No runtime value or maintenance cost exceeds benefit

| # | Item | Type | Evidence | Risk |
|---|------|------|----------|------|
| R1 | `MessageResponse` schema | Dead code | `schemas.py` line 78. Zero imports in any router or service. Grep: `rg "MessageResponse" src/` returns only the definition, no callers. | **None**. Pure dead code. |
| R2 | `scripts/dev/start-v1-api.ps1` + `stop-v1-api.ps1` | **HOLD** — restored after safety review. | Provides PID management, background process lifecycle, and log redirection. Not equivalent to `start_local_app.ps1` (foreground, no PID). Retained as unattended/headless start option. |
| R3 | `scripts/download_ecommerce_datasets.py` | **HOLD** — restored after safety review. | Downloads benchmark ecommerce datasets (Olist, Retail Rocket, UCI, Instacart). Awaiting a later domain/scenario-pack decision on whether non-manufacturing business-object test data is needed. |
| R4 | `docs/mvp-plan.md` | Superseded doc | 2-week MVP plan from project inception. Entirely superseded by Phase 1-14 delivery. | **Archived.** S1 moved to `docs/archive/mvp-plan.md`. |
| R5 | `docs/web-search-design.md` | Design-only doc | Feature classified as "Discovery" since 2026-06-17. Never implemented. | **Archived.** S1 moved to `docs/archive/web-search-design.md`. |
| R6 | `docs/agent-capability-v2-design.md` | Superseded design | 18-section V2 design document. V2.1/V2.2/V2.3 all delivered. | **Archived.** S1 moved to `docs/archive/agent-capability-v2-design.md`. |
| R7 | `docs/agent-capability-v2-review.md` | Superseded review | Pre-implementation Chinese design review. Conditions passed. | **Archived.** S1 moved. |
| R8 | `docs/agent-capability-v2.1-post-review.md` | Superseded review | V2.1 post-implementation review. | **Archived.** S1 moved. |
| R9 | `docs/agent-capability-v23-eval.md` | Superseded eval | V2.3 eval results. 39 tests. Real DeepSeek smoke. | **Archived.** S1 moved. |
| R10 | `docs/agent-eval-report.md` | Superseded eval | Agent Workflow Evaluation v1. Superseded by V2.3. | **Archived.** S1 moved. |
| R11 | `docs/rag-quality-eval-report.md` | Placeholder report | Sections never filled. Active eval scripts (`run_eval.py`, `run_rag_quality_eval.py`) still reference it. | **Deferred.** Marked as "pending regeneration." |
| R12 | `docs/research/public-agent-architecture-research.md` | Research note | 8 public projects analyzed. Adoption decisions in handoff.md. | **Archived.** S1 moved. |
| R13 | `docs/ecc-stage-prompts.md` | ECC prompt templates | ECC has been offloaded. | **Archived.** S1 moved to `docs/archive/ecc-stage-prompts.md`. |

---

## 3. Dependency Evidence & Deletion Risk Per REMOVE Item

Each REMOVE item verified with `rg`/import/route/test scans:

| Item | Grep Evidence | Import Evidence | Route Evidence | Test Evidence |
|------|--------------|----------------|---------------|---------------|
| R1 MessageResponse | `rg "MessageResponse" src/` → 1 hit: definition only | 0 imports | 0 route references | 0 test references |
| R2 start/stop-v1-api | HOLD — PID + background lifecycle, not equivalent to start_local_app | N/A (PowerShell) | N/A | N/A |
| R3 download_ecommerce | HOLD — awaiting a later domain/scenario-pack decision | N/A | N/A | 0 test imports |
| R4 mvp-plan.md | `rg "mvp-plan" docs/` → 0 cross-references | N/A | N/A | N/A |
| R5 web-search-design | `rg "web-search-design"` → 1 reference in CLAUDE.md (historical mention) | N/A | N/A | N/A |
| R6-R10 Agent docs | Each doc self-contained with no cross-references from active entry docs | N/A | N/A | N/A |
| R11 rag-quality-eval | Generated by `run_rag_quality_eval.py` (script still active) | N/A | N/A | References `docs/eval/rag-queries-ontology.json` (still active) |
| R12 research note | Self-contained, no cross-references from active docs | N/A | N/A | N/A |
| R13 ecc-stage-prompts | `rg "ecc-stage-prompts"` → 0 cross-references from active entry docs | N/A | N/A | N/A |

**Critical invariant preserved**: No models, migrations, routers, services, tests, or frontend code is in the REMOVE list. All REMOVE items are dead code, stale scripts, or superseded documentation.

---

## 4. S1 Scope — Low-Risk Cleanup Only

S1 only performs low-risk cleanup that has zero impact on product behavior. All navigation, consolidation, and hiding decisions are deferred to S2.

### S1 Final Results

| Priority | Item | Action | Status |
|----------|------|--------|--------|
| **S1-1** | R1: `MessageResponse` schema | Delete from schemas.py | ✅ Done — safe |
| **S1-2** | R2: `start/stop-v1-api.ps1` | **Restored** after safety review | ⚠️ Reversed — provides PID/background lifecycle, not equivalent to start_local_app |
| **S1-3** | R3: `download_ecommerce_datasets.py` | **Restored** after safety review | ⚠️ Reversed — awaiting a later domain/scenario-pack decision |
| **S1-4** | R4: `docs/mvp-plan.md` | Archive | ✅ Done |
| **S1-5** | R5: `docs/web-search-design.md` | Archive | ✅ Done |
| **S1-6** | R6-R10: Agent superseded docs (5 files) | Archive | ✅ Done |
| **S1-7** | R12: `public-agent-architecture-research.md` | Archive | ✅ Done |
| **S1-8** | R13: `docs/ecc-stage-prompts.md` | Archive | ✅ Done |

**Final S1 outcome**: 1 dead code removal + 9 doc archives confirmed safe. 3 utility scripts restored after safety review. Zero navigation or product behavior changes.

### Deferred from S1

| Item | Reason for Deferral |
|------|-------------------|
| R11: `rag-quality-eval-report.md` | May be regenerated from active eval scripts. Mark as "pending regeneration" — do not delete. |
| All CONSOLIDATE items (C1-C5) | Surface integration requires S2 design and implementation work. S1 is cleanup only. |
| All HIDE items (H1-H3) | Navigation changes affect user workflows. S2 evaluates after consolidation is proven. |
| Ontology nav placement | Ontology is the product north star. Its navigation position is an S2 decision requiring careful evaluation — not a simple HIDE. |

### S2 Candidates (not in S1 scope)

| Category | Items | Description |
|----------|-------|-------------|
| **Navigation reduction** | H3 | Reduce "更多工具" from 5 to 3 entries after surface consolidation |
| **Page hiding** | H1, H2 | Evaluate hiding Agent, Conversations, 问答 behind Pilot tabs |
| **Capability consolidation** | C1-C5 | Fold Tasks, RAG, Conversations, Agent, Ontology into Pilot surface |
| **Ontology nav decision** | C5 | Keep in primary nav, move to "更多工具", or integrate into Pilot — S2 decision |

---

## 5. Current Navigation (S1 — No Changes)

S1 makes no navigation changes. The current layout is preserved:

### Primary navigation:
| Entry | Route | Rationale |
|-------|-------|-----------|
| **Pilot** | `/groups/:gid/projects` | FDE main chain — default landing |
| **Ontology** | `/groups/:gid/ontology` | Product north star — stays in primary nav through S1 |
| **工作区** | `/groups` | Workspace management |

### "更多工具" dropdown (S1 unchanged — 5 entries):
| Entry | Route | Rationale |
|-------|-------|-----------|
| 问答 | `/ask` | Knowledge exploration — S2 candidate for Pilot Ask tab |
| 知识库 | `/groups/:gid/documents` | Document management for RAG evidence |
| 对话 | `/groups/:gid/conversations` | Multi-turn consultation — S2 candidate for Pilot Ask tab |
| 任务 | `/groups/:gid/tasks` | Lightweight task tracking — S2 candidate for Pilot Actions tab |
| Agent | `/groups/:gid/agent` | Controlled orchestration — S2 candidate for Pilot Advanced tab |

### Hidden (direct URL accessible, not in any nav):
| Entry | Route | Rationale |
|-------|-------|-----------|
| ETL Jobs | `/groups/:gid/jobs` | Operator troubleshooting |
| RAG Debug | `/groups/:gid/rag` | Developer debugging |

### S2 Navigation Evaluation (not S1):
- Whether to reduce primary nav from 3 to 2 entries (Ontology placement)
- Whether to reduce "更多工具" from 5 to 3 entries after surface consolidation
- Whether to hide Ask/Conversations/Agent behind Pilot tabs

---

## 6. Estimated S1 Reduction

| Category | Before | After (S1) | Delta |
|----------|--------|------------|-------|
| Dead code (schema) | 1 orphan | 0 orphan | -1 |
| Superseded docs archived | 1 in archive | 10 in archive | 9 moved to archive |
| Tools restored after review | — | 3 scripts retained | +3 (safety correction) |
| **Total net effect** | — | — | **1 removal + 9 archives + 3 restorations** |
| **Navigation changes** | — | — | **0** (deferred to S2) |
| **Frontend LOC change** | — | — | **0** (no navbar.js changes in S1) |

**S1 is a cleanup-only pass.** Navigation reduction, page hiding, and capability consolidation are S2 scope.

---

## 7. What Must NOT Be Deleted (S1 or later)

| Category | Items | Reason |
|----------|-------|--------|
| **All database models** | 27 models in `models.py` | Data integrity — existing databases depend on these |
| **All migrations** | 23 migration files (`0018`–`0023`) | Irreversible schema history |
| **All backend routers** | 11 routers | All have active tests, all are registered in `main.py`, all are functional |
| **All backend services** | 20 services | All have callers (routers or other services) |
| **All pytest tests** | `tests/` (749 tests) | Regression protection |
| **All frontend pages** | 17 JS files | All are reachable via routes or dynamic imports — no orphan pages |
| **All E2E tests** | `tests/e2e/` (18 tests) | Browser verification |
| **Active demo scripts** | 5 ontology/manufacturing demo scripts | Portfolio evidence, reproducible |
| **Active ops scripts** | `scripts/docker/start-api.sh`, `bootstrap-ubuntu.sh`, `smoke-cloud.sh`, `start_local_app.ps1`, `start_local_preview.ps1`, `start/stop-v1-api.ps1` | Deployment and development |
| **Active eval scripts** | `evaluate.py`, `run_eval.py`, `check_eval_thresholds.py`, `run_rag_quality_eval.py` | Retrieval quality measurement |
| **Active quality scripts** | `verify_ui.py`, `screenshots_f2b.py`, `check_doc_alignment.py`, `scan_encoding.py` | Verification |
| **Active product docs** | `PRODUCT.md`, `product-alignment-prd.md`, `agent-handoff.md`, `project-roadmap.md`, `project-status.toml`, `development-workflow.md`, `quality-gate.md`, `interview-demo-questions.md` | Product narrative |
| **Phase planning docs** | `phase14-planning.md`, `frontend-f2-planning.md`, `phase13-planning.md`, `phase13-review.md`, `phase12-planning.md`, `phase11-planning.md`, `phase10-planning.md` | Phase delivery history — not runtime redundancy |
| **Code maps** | `CODEMAPS/*.md` | Onboarding |
| **Eval data** | `docs/eval/*.json` | Active eval queries |
| **Engineering memory** | `highlight-log.md`, `pitfall-log.md`, `learning-index.md` | Ongoing learning |
| **Deployment docs** | `deployment-v3-cloud.md`, `cloud-smoke-playbook.md` | Operations |
| **Boundary docs** | `mcp-agent-boundary-design.md`, `ontology-agent-boundary.md` | Design constraints |

---

## 8. Known Documents — NOT Classified as Redundant

The following are historical delivery records, not runtime redundancy. They are preserved as phase evidence:

- All `docs/phase*.md` planning and review documents
- All `docs/engineering-memory/` retrospective and learning files
- All `docs/ontology-*-demo-report.md` demo artifacts
- `docs/frontend-redesign-plan.md` (superseded by F2, but records design decisions)
- `docs/project-workflows.md` (documents internal processes)
- `docs/CODEMAPS/*.md` (code navigation)

---

## 9. S2 Product-Surface Consolidation Design

### Decision

Do not collapse every capability into Pilot tabs. The current standalone tools
are group-scoped, while Pilot is project-scoped. Presenting them inside a Pilot
without a real `project_id` contract would create a false integration and make
isolation, provenance, and audit behavior harder to explain.

The product surface has two levels:

1. **Pilot** is the guided FDE delivery path for one business problem.
2. **Ontology** is the shared semantic asset and governance workspace for the group.

Workspace selection remains global context. Evidence, conversations, tasks, and
Agent workflows remain supporting capabilities until they gain explicit project
scope or a deliberate cross-project role.

### Navigation Decision

| Surface | S2 decision | Reason |
|---------|-------------|--------|
| Pilot | Keep in primary navigation and as default landing | Main guided delivery path |
| Ontology | Keep in primary navigation | Product north star and group-level governance surface |
| Workspace | Keep in primary navigation | Group and permission context |
| Knowledge Base | Keep in More Tools; add contextual Pilot links in S2.1 | Evidence source is group-scoped |
| Ask | Keep in More Tools; add contextual Pilot link in S2.1 | Useful for problem framing but not project-scoped |
| Conversations | Keep unchanged | No `project_id`; no replacement exists |
| Tasks | Keep unchanged | No `project_id`; cannot yet represent Pilot actions safely |
| Agent | Keep unchanged as an advanced supporting tool | No project scope; existing HITL and audit remain valuable |
| ETL Jobs / RAG Debug | Keep direct-route operator tools | Not part of normal user navigation |

No navigation entry is hidden or removed in S2.1.

### Stage Guidance Contract

Each Pilot stage exposes one primary action and only relevant supporting paths.
Supporting links navigate to existing capabilities; they do not imply that the
resulting records are already attached to the project.

| Pilot stage | Primary action | Supporting path |
|-------------|----------------|-----------------|
| Goal | Upload the first dataset | Open Knowledge Base or Ask to clarify the business problem |
| Data | Upload more data / generate model drafts | Inspect source data profile |
| Model | Review and accept drafts | Open Ontology governance for shared semantic context |
| Validate | Build package, generate bindings, activate | Inspect quality and provenance already shown in the stage |
| Pilot | Query the activated runtime | Keep measurement/iteration as an explicit future gap |

### Implementation Slices

| Slice | Lane | Scope | Exit condition |
|-------|------|-------|----------------|
| S2.1 Contextual guidance | Standard | Frontend links and concise stage guidance only; no API/schema change | A new user can identify the next action and relevant support path from each stage |
| S2.2 Project evidence contract | Safety | Design and, only after approval, persist explicit project-to-evidence linkage | Evidence association is group-checked, project-scoped, auditable, and provenance-preserving |
| S2.3 Project work context | Safety | Evaluate optional `project_id` for conversations, tasks, and Agent runs | No cross-project leakage; existing group-scoped flows remain compatible |
| S2.4 Navigation consolidation | Standard | Hide or regroup standalone entries only after replacement parity | Direct routes remain compatible and tests prove replacement workflows |

### S2.1 Boundaries

- No backend, API, schema, migration, permission, or audit changes.
- No page deletion or route removal.
- No new tabs that duplicate full standalone applications.
- No MCP runtime, Graph RAG, Agent auto-write, or new dependency.
- Do not claim project linkage when the underlying record is only group-scoped.
- Keep the Swiss visual system; this is workflow guidance, not another redesign.
- Keep `download_ecommerce_datasets.py` on HOLD. Domain/scenario-pack selection is
  a separate product decision, not part of S2 surface consolidation.

### Acceptance Signals

- Dataset-first users can continue directly through the five-stage Pilot.
- Problem-first users can discover Knowledge Base and Ask from the Goal stage.
- Ontology remains visibly central without competing with the Pilot sequence.
- Every stage has a clear primary action; supporting tools are secondary.
- Nothing is hidden before an equivalent project-scoped path exists.

### S2.1 Delivered

Actual changes (3 files, +27 lines):

- `static/js/pages/project.js`:
  - Goal stage: added `.stageSupport` area with `#goalKnowledgeLink` (→ `#/groups/{gid}/documents`) and `#goalAskLink` (→ `#/ask`). Copy explicitly states links are not yet project-scoped.
  - Data stage: `#genFromDataBtn` now has class `primary`, `#uploadMoreBtn` now has class `secondary`.

- `static/js/pages/project-model.js`:
  - Model stage: added `.stageSupport` area with `#modelOntologyLink` (→ `#/groups/{gid}/ontology`). Copy states this is group-level governance context.

- `static/styles.css`:
  - Added `.stageSupport` (border-top separator, flex-wrap, gap) and `.supportLink` (inline border, radius ≤ 6px, hover to brand-light).

- `scripts/verify_ui.py`:
  - 6 new checks: Goal knowledge/ask link href correctness, Data stage primary/secondary button class verification, Model ontology link href correctness.

No backend, API, schema, migration, permission, route, navigation, or page changes.
