# Product Rationalization Review — S0 Audit

Date: 2026-06-20
Status: S0 audit complete. No code deleted. S1 scope pending approval.

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
| K12 | Deployment scripts | Scripts | `start-api.sh`, `bootstrap-ubuntu.sh`, `smoke-cloud.sh`, `start_local_app.ps1` | Operations |
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
| R2 | `scripts/dev/start-v1-api.ps1` + `stop-v1-api.ps1` | Stale scripts | Named "v1" but start current app. Superseded by `scripts/start_local_app.ps1`. PID-file pattern is vestigial — no other script uses `.runtime/` PID files. | **None**. `start_local_app.ps1` provides the same functionality. |
| R3 | `scripts/download_ecommerce_datasets.py` | Niche script | Downloads Olist/Retail Rocket/UCI/Instacart datasets via KaggleHub. Not referenced by any test, demo, or pipeline script. Requires `kagglehub` pip package (not in requirements.txt). | **None**. Manufacturing dataset generator (`generate_manufacturing_dataset.py`) covers Pilot demo data needs. |
| R4 | `docs/mvp-plan.md` | Superseded doc | 2-week MVP plan from project inception. Entirely superseded by Phase 1-14 delivery. References concepts that no longer exist in the current product. | **None**. Historical record of project origin — archive if desired. |
| R5 | `docs/web-search-design.md` | Design-only doc | Feature classified as "Discovery" since 2026-06-17. Never implemented. No backend router, service, or frontend page. `project-status.toml` confirms "not started." | **None**. Retaining design for future reference is optional. |
| R6 | `docs/agent-capability-v2-design.md` | Superseded design | 18-section V2 design document. V2.1/V2.2/V2.3 all delivered per agent-handoff.md. Current implementation differs from design in several documented ways (post-review docs capture final state). | **Low**. Archive if removed; current agent behavior is documented in handoff.md and test files. |
| R7 | `docs/agent-capability-v2-review.md` | Superseded review | Pre-implementation Chinese design review. Conditions passed. Implementation complete. | **Low**. Archive. |
| R8 | `docs/agent-capability-v2.1-post-review.md` | Superseded review | V2.1 post-implementation review. Version superseded by V2.2/V2.3. | **Low**. Archive. |
| R9 | `docs/agent-capability-v23-eval.md` | Superseded eval | V2.3 eval results. 39 tests. Real DeepSeek smoke. Historical evidence that the eval was done, but the results are captured in handoff.md. | **Low**. Archive. |
| R10 | `docs/agent-eval-report.md` | Superseded eval | Agent Workflow Evaluation v1. Superseded by V2.3 eval (`agent-capability-v23-eval.md`). | **Low**. Archive. |
| R11 | `docs/rag-quality-eval-report.md` | Placeholder report | Contains "Populated by scripts/..." sections never filled. Baseline only. The scripts that generate it (`run_eval.py`, `run_rag_quality_eval.py`) are still active. | **Deferred**. Do NOT delete in S1. Mark as "regenerate from scripts" — report content may be regenerated in the future. |
| R12 | `docs/research/public-agent-architecture-research.md` | Research note | 8 public projects analyzed. Adoption decisions recorded in handoff.md. Useful as historical reference but not active documentation. | **Low**. Archive. |
| R13 | `docs/ecc-stage-prompts.md` | ECC prompt templates | Saved ECC plan prompts for major phases. ECC has been offloaded — this file is no longer operationally relevant. | **Low**. Archive. |

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
| R13 ecc-stage-prompts | `rg "ecc-stage-prompts"` → 0 cross-references from active entry docs | N/A | N/A | N/A |

**Critical invariant preserved**: No models, migrations, routers, services, tests, or frontend code is in the REMOVE list. All REMOVE items are dead code, stale scripts, or superseded documentation.

---

## 4. S1 Scope — Low-Risk Cleanup Only

S1 only performs low-risk cleanup that has zero impact on product behavior. All navigation, consolidation, and hiding decisions are deferred to S2.

### S1 Approved Actions (low-risk, no product behavior change)

| Priority | Item | Action | Risk | Verification |
|----------|------|--------|------|-------------|
| **S1-1** | R1: `MessageResponse` schema | Delete from schemas.py | Zero | ruff check; full pytest shows no import failures |
| **S1-2** | R2: `start/stop-v1-api.ps1` | Delete both scripts | Zero | None — `start_local_app.ps1` provides equivalent function |
| **S1-3** | R3: `download_ecommerce_datasets.py` | Delete | Zero | None — no test/demo/pipeline references |
| **S1-4** | R4: `docs/mvp-plan.md` | Move to `docs/archive/` | Zero | check_doc_alignment.py |
| **S1-5** | R5: `docs/web-search-design.md` | Move to `docs/archive/` | Zero | Remove stale cross-reference from CLAUDE.md |
| **S1-6** | R6-R10: Agent superseded docs (5 files) | Move to `docs/archive/` | Low | Verify handoff.md captures final agent state |
| **S1-7** | R12: `public-agent-architecture-research.md` | Move to `docs/archive/` | Low | None |
| **S1-8** | R13: `docs/ecc-stage-prompts.md` | Move to `docs/archive/` | Low | ECC has been offloaded |

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
| Stale scripts | 2 | 0 | -2 |
| Niche scripts | 1 | 0 | -1 |
| Superseded docs archived | 0 in archive | 8 moved to archive | -8 from active docs |
| **Total files affected** | — | — | **12 files** (1 delete, 2 delete, 1 delete, 8 archive) |
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
