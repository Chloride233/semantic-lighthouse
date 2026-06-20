# Product Rationalization Review — S0 Audit

Date: 2026-06-20
Status: S0 audit complete. No code deleted. S1 scope pending approval.

## 1. FDE Main Chain Definition

The product's **Frontend-Driven Enterprise (FDE) main chain** is the Phase 14 Guided Pilot five-stage flow:

```
目标 (goal) → 数据 (data) → 模型 (model) → 验证 (validate) → Pilot (pilot)
```

**Primary user path**: Login → Workspace → Pilot list → Create project → Upload CSV/XLSX → Generate model drafts → Batch review → Build package → Generate bindings → Activate → Query runtime

**Essential backend routers** (4): `projects.py`, `datasets.py`, `ontology.py` (main + project_model_router), `runtime.py`

**Essential frontend pages** (6): `project.js`, `project-model.js`, `project-validate.js`, `project-pilot.js`, `project-dialog.js`, `projects.js`

**Mandatory infrastructure** (2 routers, 3 services): `auth.py`, `groups.py`, `embeddings.py`, `chat.py`, `retrieval.py`

**Ontology governance pipeline** (feeds model stage): `ontology.py` service, `ontology_drafts.py`, `ontology_draft_reviews.py`, `ontology_draft_quality.py`, `ontology_packages.py`, `business_contract_validator.py`, `business_contract_compiler.py`

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
| K12 | Deployment scripts | Scripts | `start-api.sh`, `bootstrap-ubuntu.sh`, `smoke-cloud.sh`, `start_local_app.ps1` | Operations |
| K13 | Eval harness | Scripts | `evaluate.py`, `run_eval.py`, `check_eval_thresholds.py`, `run_rag_quality_eval.py` | Retrieval quality measurement |
| K14 | Product definition docs | Docs | `PRODUCT.md`, `product-alignment-prd.md`, `agent-handoff.md`, `project-roadmap.md`, `interview-demo-questions.md` | Product narrative |
| K15 | Engineering memory | Docs | `highlight-log.md`, `pitfall-log.md`, `learning-index.md` | Ongoing learning |

### CONSOLIDATE — Valuable but should fold into main flow

| # | Capability | Current State | Consolidation Target |
|---|-----------|---------------|---------------------|
| C1 | Tasks (轻量任务) | Independent page at `/tasks`, in "更多工具" dropdown | Pilot "Actions" tab — confirmed next steps appear here |
| C2 | RAG Answer (知识问答) | Independent page at `/ask`, in "更多工具" dropdown | Pilot "Ask" tab in goal stage — knowledge exploration before project creation |
| C3 | Conversations (多轮对话) | Independent page at `/conversations`, in "更多工具" dropdown | Fold into Pilot "Ask" tab as session history |
| C4 | Agent console | Independent page at `/agent`, in "更多工具" dropdown | Pilot "Advanced" tab — only visible for complex multi-step workflows |
| C5 | Ontology standalone workspace | Independent page at `/ontology`, primary nav entry | Keep backend, move to "更多工具" or "Ontology" secondary tab in Pilot |

### HIDE — Keep backend, remove from user-facing navigation

| # | Capability | Backend | UI Action |
|---|-----------|---------|-----------|
| H1 | ETL Jobs page | Keep `documents.py` jobs endpoints | Already hidden — no nav entry. Keep for operator troubleshooting. |
| H2 | RAG Debug console | Keep `rag.py` router | Already hidden — no nav entry. Keep for developer debugging. |
| H3 | Agent console | Keep `agent.py` router, all services, all tests | Move from "更多工具" to hidden (direct URL only). Backend is portfolio evidence. |
| H4 | Conversations standalone | Keep `conversations.py` router | Move from "更多工具" to hidden. Functionality moved to Pilot Ask tab. |
| H5 | "更多工具" dropdown | — | Reduce to 3 entries: 知识库, 任务, Ontology. Remove 问答, 对话, Agent. |

### REMOVE — No runtime value or maintenance cost exceeds benefit

| # | Item | Type | Evidence | Risk |
|---|------|------|----------|------|
| R1 | `MessageResponse` schema | Dead code | `schemas.py` line 78. Zero imports in any router or service. Grep: `rg "MessageResponse" src/` returns only the definition, no callers. | **None**. Pure dead code. |
| R2 | `scripts/dev/start-v1-api.ps1` + `stop-v1-api.ps1` | Stale scripts | Named "v1" but start current app. Superseded by `scripts/start_local_app.ps1`. PID-file pattern is vestigial — no other script uses `.runtime/` PID files. | **None**. `start_local_app.ps1` provides the same functionality. |
| R3 | `scripts/download_ecommerce_datasets.py` | Niche script | Downloads Olist/Retail Rocket/UCI/Instacart datasets via KaggleHub. Not referenced by any test, demo, or pipeline script. Requires `kagglehub` pip package (not in requirements.txt). | **None**. Manufacturing dataset generator (`generate_manufacturing_dataset.py`) covers Pilot demo data needs. |
| R4 | `docs/mvp-plan.md` | Superseded doc | 2-week MVP plan from project inception. Entirely superseded by Phase 1-14 delivery. References concepts that no longer exist in the current product. | **None**. Historical record of project origin — archive if desired. |
| R5 | `docs/web-search-design.md` | Design-only doc | Feature classified as "Discovery" since 2026-06-17. Never implemented. No backend router, service, or frontend page. `project-status.toml` confirms "not started." | **None**. Retaining design for future reference is optional. |
| R6 | `docs/agent-capability-v2-design.md` | Superseded design | 18-section V2 design document. V2.1/V2.2/V2.3 all delivered per agent-handoff.md. Current implementation differs from design in several documented ways (post-review docs capture final state). | **Low**. Archive if removed; current agent behavior is documented in handoff.md and test files. |
| R7 | `docs/agent-capability-v2-review.md` | Superseded review | Pre-implementation Chinese design review. Conditions passed. Implementation complete. | **Low**. Archive. |
| R8 | `docs/agent-capability-v2.1-post-review.md` | Superseded review | V2.1 post-implementation review. Version superseded by V2.2/V2.3. | **Low**. Archive. |
| R9 | `docs/agent-capability-v23-eval.md` | Superseded eval | V2.3 eval results. 39 tests. Real DeepSeek smoke. Historical evidence that the eval was done, but the results are captured in handoff.md. | **Low**. Archive. |
| R10 | `docs/agent-eval-report.md` | Superseded eval | Agent Workflow Evaluation v1. Superseded by V2.3 eval (`agent-capability-v23-eval.md`). | **Low**. Archive. |
| R11 | `docs/rag-quality-eval-report.md` | Placeholder report | Contains "Populated by scripts/..." sections never filled. Baseline only. The scripts that generate it (`run_eval.py`, `run_rag_quality_eval.py`) are still active. Report content is stale. | **Low**. Regenerate from scripts if needed. |
| R12 | `docs/research/public-agent-architecture-research.md` | Research note | 8 public projects analyzed. Adoption decisions recorded in handoff.md. Useful as historical reference but not active documentation. | **Low**. Archive. |

---

## 3. Dependency Evidence & Deletion Risk Per REMOVE Item

Each REMOVE item verified with `rg`/import/route/test scans:

| Item | Grep Evidence | Import Evidence | Route Evidence | Test Evidence |
|------|--------------|----------------|---------------|---------------|
| R1 MessageResponse | `rg "MessageResponse" src/` → 1 hit: definition only | 0 imports | 0 route references | 0 test references |
| R2 start/stop-v1-api | Not referenced by any other script | N/A (PowerShell) | N/A | N/A |
| R3 download_ecommerce | `rg "download_ecommerce"` → 0 references outside the file | N/A | N/A | 0 test imports |
| R4 mvp-plan.md | `rg "mvp-plan" docs/` → 0 cross-references | N/A | N/A | N/A |
| R5 web-search-design | `rg "web-search-design"` → 1 reference in CLAUDE.md (historical mention) | N/A | N/A | N/A |
| R6-R10 Agent docs | Each doc self-contained with no cross-references from active entry docs | N/A | N/A | N/A |
| R11 rag-quality-eval | Generated by `run_rag_quality_eval.py` (script still active) | N/A | N/A | References `docs/eval/rag-queries-ontology.json` (still active) |
| R12 research note | Self-contained, no cross-references from active docs | N/A | N/A | N/A |

**Critical invariant preserved**: No models, migrations, routers, services, tests, or frontend code is in the REMOVE list. All REMOVE items are dead code, stale scripts, or superseded documentation.

---

## 4. S1 Recommended Deletion List (low-risk → higher-risk)

Ordered by risk. All below are S1 candidates — none deleted in S0.

| Priority | Item | Risk | LOC/Pages Affected | Verification Needed |
|----------|------|------|-------------------|-------------------|
| **P1** | R1: `MessageResponse` schema | Zero | ~3 lines in schemas.py | ruff check |
| **P2** | R2: `start/stop-v1-api.ps1` | Zero | 2 script files | None |
| **P3** | R3: `download_ecommerce_datasets.py` | Zero | 1 script file | None |
| **P4** | R4: `docs/mvp-plan.md` | Zero | 1 doc file | check_doc_alignment.py |
| **P5** | R5: `docs/web-search-design.md` | Near-zero | 1 doc file | Update CLAUDE.md cross-reference |
| **P6** | R6-R10: Agent superseded docs (5 files) | Low | 5 doc files | Verify handoff.md captures final agent state |
| **P7** | R11: `rag-quality-eval-report.md` | Low | 1 doc file | Regenerate from scripts/run_rag_quality_eval.py if needed |
| **P8** | R12: public-agent-architecture-research.md | Low | 1 doc file | None |
| **P9** | H3-H5: Hide Agent, Conversations, "问答" from nav | Medium | navbar.js (~10 lines) | verify_ui, E2E navigation tests |
| **P10** | H4: Reduce "更多工具" to 3 entries | Medium | navbar.js (~5 lines) | verify_ui, E2E |
| **P11** | C5: Move Ontology from primary nav to "更多工具" | Medium | navbar.js (~3 lines) | verify_ui, E2E |

---

## 5. Recommended Minimum Product Navigation

After S1 consolidation:

### Primary navigation (always visible):
| Entry | Route | Rationale |
|-------|-------|-----------|
| **Pilot** | `/groups/:gid/projects` | FDE main chain — default landing |
| **工作区** | `/groups` | Workspace management |

### "更多工具" dropdown (reduced to 3):
| Entry | Route | Rationale |
|-------|-------|-----------|
| **知识库** | `/groups/:gid/documents` | Document management for RAG evidence |
| **任务** | `/groups/:gid/tasks` | Lightweight task tracking |
| **Ontology** | `/groups/:gid/ontology` | Moved from primary nav — governance workspace |

### Hidden (direct URL accessible, not in any nav):
| Entry | Route | Rationale |
|-------|-------|-----------|
| 问答 | `/ask` | Folded into Pilot Ask tab (C2) |
| 对话 | `/groups/:gid/conversations` | Folded into Pilot Ask tab (C3) |
| Agent | `/groups/:gid/agent` | Backend portfolio evidence, hidden UI |
| ETL Jobs | `/groups/:gid/jobs` | Already hidden, operator only |
| RAG Debug | `/groups/:gid/rag` | Already hidden, developer only |

---

## 6. Estimated Reduction

| Category | Before | After | Delta |
|----------|--------|-------|-------|
| Primary nav entries | 3 | 2 | -1 (Ontology moved) |
| "更多工具" entries | 5 | 3 | -2 (问答, 对话, Agent hidden) |
| Dead code (schema) | 1 orphan | 0 orphan | -1 |
| Stale scripts | 2 | 0 | -2 |
| Niche scripts | 1 | 0 | -1 |
| Superseded docs | 9 | 0–3 (archived) | -6 to -9 |
| **Total files affected** | — | — | **12–15 files** |
| **Pages hidden from nav** | — | — | **3 pages** (问答, 对话, Agent) |
| **Frontend LOC change** | — | — | **~15 lines** (navbar.js only) |

**LOC reduction is NOT the goal.** The goal is simpler user navigation and fewer maintenance surfaces.

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
| **Active ops scripts** | `start-api.sh`, `bootstrap-ubuntu.sh`, `smoke-cloud.sh`, `start_local_app.ps1`, `start_local_preview.ps1` | Deployment and development |
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
- `docs/ecc-stage-prompts.md` (records ECC prompt templates)
- `docs/CODEMAPS/*.md` (code navigation)
