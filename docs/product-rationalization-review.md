# Product Rationalization and Surface Consolidation Review

Date: 2026-06-20
Status: S2.4 backend consolidation closed. S2.4D/E/F remain deferred candidates, not automatic next work.

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

---

## 10. S2.2 Project Evidence Contract

Status: Delivered and safety-reviewed. Frontend integration remains deferred to S2.4.

### Decision Summary

**Chosen approach**: Single `ProjectEvidenceLink` table with polymorphic `evidence_type` + `evidence_id`. Server-side type-specific validation. No multi-table inheritance. No DB-level foreign keys to evidence sources.

**Rejected alternatives**:
- **Multiple join tables** (`project_document_links`, `project_ragrun_links`): Adds migration and API surface for each new evidence type. No clear benefit over a single table with a type discriminator, since all evidence types share the same lifecycle (associate, list, archive, audit).
- **JSON column on BusinessProject**: Cannot index, cannot query "all projects linked to document X," and mixes project metadata with relational evidence.
- **Reuse `evidence_refs` on OntologyModelingDraft**: Draft-level evidence is about column-to-dataset lineage, not project-level knowledge grounding. Different granularity, different lifecycle, different UX.

### 10.1 Read Model

**Table**: `project_evidence_links` (migration `0024`)

| Column | Type | Constraints | Purpose |
|--------|------|-------------|---------|
| `id` | String(36) | PK, default=new_id | Standard UUID primary key |
| `group_id` | String(36) | FK groups.id, indexed, NOT NULL | Group isolation — never trust client-supplied |
| `project_id` | String(36) | FK business_projects.id, indexed, NOT NULL | Project scope |
| `evidence_type` | String(20) | NOT NULL | `document` or `rag_run` (extensible) |
| `evidence_id` | String(36) | NOT NULL | ID of the Document or RAGRun |
| `role` | String(20) | NOT NULL | Controlled: `context`, `requirement`, `decision`, `validation` |
| `note` | String(500) | NULLABLE, trimmed | Optional FDE annotation |
| `status` | String(20) | NOT NULL, default="active" | `active` or `removed` |
| `created_by` | String(36) | FK users.id, NOT NULL | Who created the link |
| `created_at` | DateTime(tz=True) | NOT NULL, default=utc_now | Creation timestamp |
| `updated_at` | DateTime(tz=True) | NOT NULL, default=utc_now | Last state change (create, relink) |
| `removed_by` | String(36) | NULLABLE | Who removed the link |
| `removed_at` | DateTime(tz=True) | NULLABLE | Removal timestamp |

**Unique constraint**: `(project_id, evidence_type, evidence_id)` — prevents duplicate links for the same evidence to the same project.

**No cascade deletes**. An explicit user unlink sets `status='removed'` + audit fields. Deleting a Document or RAGRun does not mutate the link row: it remains `active`, while GET derives `evidence_status='gone'` and `unavailable=true`.

### 10.2 Polymorphic evidence_id Validation

Since `evidence_id` references different tables depending on `evidence_type`, DB-level foreign keys are not used. Instead:

**On CREATE**:
1. Validate `evidence_type` is in allowed set (`document`, `rag_run`). Invalid type → 422.
2. Validate `role` is in controlled vocabulary (`context`, `requirement`, `decision`, `validation`). Invalid role → 422.
3. Query the evidence table by `evidence_id`.
4. Assert the evidence row exists AND `evidence.group_id == project.group_id` (both from the URL route). Not found or cross-group → 404.
5. Document: only `status=ready` is linkable. RAGRun: only `status=success` is linkable. Archived/failed/no_evidence evidence → 409.
6. Check existing link: active duplicate → 200 (idempotent, no audit). Removed link → reactivate same row with `evidence_relink` audit → 200.

This pattern is consistent with `OntologyModelingDraft.evidence_refs` validation (which checks `source_entity_id`/`source_relation_id`/`source_issue_id` by querying the respective tables within the same group).

### 10.3 Permissions and Isolation

| Operation | Permission | Isolation Check |
|-----------|-----------|----------------|
| `POST` (create link) | Owner or admin of the group | `group_id` from route; `project.group_id == group_id`; `evidence.group_id == group_id` |
| `GET` (list links) | Member+ | `group_id` from route; `project.group_id == group_id` |
| `DELETE` (archive link) | Owner or admin of the group | Same as create; sets `status='removed'` |

**Hard rules**:
- `group_id` in the request body is always ignored — it comes from the URL path.
- User not a member of the route group: 403 (from `get_membership_or_404`).
- User IS a member, but project/evidence/link belongs to a different group or project: 404 (no existence leak to authorized group members).
- New links only accept `Document.status=ready` and `RagRun.status=success`. Archived/failed/no_evidence evidence returns 409.
- Existing links survive evidence archival — provenance shows `evidence_status: "archived"` or `"error"`.
- Agent runs cannot call the evidence link API. No tool registration for evidence operations.
- Goal stage knowledge base/ask links remain navigation-only — they do not auto-create evidence links.

### 10.4 Lifecycle

| Scenario | Behavior |
|----------|----------|
| Document archived (status=archived) | Existing links remain `active`. List provenance shows `evidence_status: "archived"`. New links to archived documents → 409. |
| RAG run failed (status=error or no_evidence) | Existing links remain `active`. List provenance shows `evidence_status: "error"`. New links to failed/no_evidence runs → 409. |
| Project archived | Existing links remain — project archive does not cascade. List endpoint still works. Creating new links to archived projects returns 409. |
| Active duplicate link | Second POST with same `(project_id, evidence_type, evidence_id)` and existing link `status=active` returns 200 with the existing record. No new audit row. |
| Removed link re-POST | Existing link with `status=removed` is reactivated: `status` → `active`, `removed_by`/`removed_at` cleared, `updated_at` set. Audit: `evidence_relink`. Returns 200. |
| Source evidence deleted | `ProjectEvidenceLink.status` stays `active`. GET dynamically returns `evidence_status: "gone"` / `unavailable: true`. Link is NOT auto-set to `removed` — `removed` only means the user explicitly unlinked. |
| Remove link | `status` → `removed`, `removed_by` and `removed_at` set. Original evidence never deleted. Link row never physically deleted. Audit: `evidence_unlink`. |
| List removed links | Default list returns only `active`. Query parameter `?status=removed` or `?status=all` includes removed links. |
| Audit | Every state transition creates an `OntologyRuntimeAudit` record. `operation`: `evidence_link` / `evidence_unlink` / `evidence_relink`. `object_type` stores `document` or `rag_run`. `field_names` stores only field name strings: `["evidence_type", "role", "note", "status"]` — never field values, IDs, paths, or secrets. `project_id` is a dedicated column. `error_summary` never contains evidence_id, note text, file paths, raw_content, or prompts. |

### 10.5 Provenance Summary

The list response for each link includes:

```json
{
  "id": "...",
  "evidence_type": "document",
  "evidence_id": "...",
  "role": "context",
  "note": "Industry whitepaper referenced in goal stage",
  "status": "active",
  "created_by": "...",
  "created_at": "...",
  "provenance": {
    "evidence_title": "Enterprise Ontology Design",
    "evidence_status": "ready",
    "evidence_created_at": "..."
  }
}
```

For Document evidence, `provenance` returns only: `title`, `status`, `file_name`, `source_label` (frontmatter `source` or `title`), `created_at`. Never: absolute paths, `source_path`, `storage_path`, `raw_content`.

For RAGRun evidence, `provenance` returns only: `question` (truncated 120 chars), `confidence`, `retrieval_method`, `citation_count`. Never: `answer`, `citations[].snippet`, `prompt`, `error_message`.

**Never exposed in any response**: `raw_content`, `storage_path`, `source_path`, `original_storage_path`, `answer`, `citations[].snippet`, `prompt`, `error_message`, `secret`, `token`.

### 10.6 API Draft

**`POST /groups/{group_id}/projects/{project_id}/evidence-links`**

Request:
```json
{
  "evidence_type": "document",
  "evidence_id": "abc123...",
  "role": "context",
  "note": "Referenced during goal definition"
}
```

Validation:
1. `require_group_role(db, user_id, group_id, {"owner", "admin"})` — 403 if not owner/admin.
2. `_get_project_or_404(db, project_id, group_id)` — 404 if project not in group.
3. If project.status == "archived" → 409.
4. Validate `evidence_type` ∈ {document, rag_run} → 422.
5. Validate `role` ∈ {context, requirement, decision, validation} → 422.
6. Query evidence by evidence_id. If not found or `evidence.group_id != group_id` → 404.
7. Validate evidence status: Document → must be `ready`. RAGRun → must be `success`. Otherwise → 409.
8. Check existing link: active → 200 (idempotent). Removed → reactivate with `evidence_relink` audit → 200. Neither → create new with `evidence_link` audit → 201.

Response (201 or 200):
```json
{
  "id": "...",
  "project_id": "...",
  "evidence_type": "document",
  "evidence_id": "...",
  "role": "context",
  "note": "Referenced during goal definition",
  "status": "active",
  "created_by": "...",
  "created_at": "...",
  "provenance": { ... }
}
```

**`GET /groups/{group_id}/projects/{project_id}/evidence-links`**

Query params: `?status=active` (default), `?status=removed`, `?status=all`, `?evidence_type=document`, `?limit=20`, `?offset=0`.

Response (200):
```json
{
  "links": [ { ... } ],
  "total": 5,
  "limit": 20,
  "offset": 0
}
```

**`DELETE /groups/{group_id}/projects/{project_id}/evidence-links/{link_id}`**

No request body. Sets `status='removed'`, `removed_by`, `removed_at`. Creates audit record. Returns 200 with the updated link. Idempotent — deleting an already-removed link returns 200 (no error).

Errors: 404 if link not found or `link.project_id != project_id` or `link.group_id != group_id`. 403 if not owner/admin.

### 10.7 UI Boundaries (Future S2.4)

- Goal stage may show a "Project Evidence" summary below the existing support links, listing linked documents and RAG runs with their provenance summaries.
- Users explicitly select "关联到 Pilot" from the knowledge base document list or from a RAG answer card. This is a deliberate action, not automatic.
- The evidence panel does not embed the full Documents page or RAG console — it shows summaries with links to the standalone pages.
- No standalone page is hidden until the project-scoped panel reaches replacement parity.

### 10.8 Original Test Plan (26 tests)

| # | Test | Lane |
|---|------|------|
| 1 | Owner creates evidence link (ready document) — 201 | Safety |
| 2 | Owner creates evidence link (success rag_run) — 201 | Safety |
| 3 | Admin creates evidence link — 201 | Safety |
| 4 | Member cannot create — 403 | Safety |
| 5 | Non-member cannot create — 403 | Safety |
| 6 | Cross-group project returns 404 (user is member of route group) | Safety |
| 7 | Cross-group evidence returns 404 (no existence leak) | Safety |
| 8 | Invalid evidence_type returns 422 | Safety |
| 9 | Invalid role returns 422 | Safety |
| 10 | Active duplicate POST returns 200 with existing record (no audit) | Safety |
| 11 | Removed link re-POST reactivates row, clears removed_*, records evidence_relink | Safety |
| 12 | Archived document new link returns 409 | Safety |
| 13 | Failed/no_evidence RAG run new link returns 409 | Safety |
| 14 | Archived project rejects new links — 409 | Safety |
| 15 | Member can list links for their group's project | Safety |
| 16 | Non-member cannot list links — 403 | Safety |
| 17 | Cross-project link listing returns 404 | Safety |
| 18 | Owner removes link — status=removed, removed_* set, evidence_unlink audit | Safety |
| 19 | Member cannot remove link — 403 | Safety |
| 20 | Double remove is idempotent — 200 | Safety |
| 21 | List with status=removed returns removed links | Safety |
| 22 | Provenance for document excludes source_path, storage_path, raw_content | Safety |
| 23 | Provenance for RAG run excludes answer, snippet, prompt, error_message | Safety |
| 24 | Audit field_names contains only field name strings, no values or IDs | Safety |
| 25 | Agent tool registry does not include evidence link operations | Safety |
| 26 | Audit row written on evidence_link, evidence_unlink, and evidence_relink | Safety |

### 10.9 Rejected Design Alternatives

| Alternative | Why Rejected |
|-------------|-------------|
| Multiple join tables per evidence type | Doubles migration and API surface per type. All evidence types share identical lifecycle — type discriminator is simpler. |
| DB-level foreign keys to documents/rag_runs | Polymorphic FK not supported in standard SQL without complex CHECK constraints. Server-side validation already proven in OntologyModelingDraft.evidence_refs. |
| JSON column on BusinessProject | Unindexable. Cannot query "which projects link to document X." Mixes project metadata with evidence. |
| Auto-link from Goal stage navigation | Violates explicit user action requirement. Goal links are discovery, not commitment. FDE must deliberately choose to associate evidence. |
| Soft-delete via a separate `removed_links` table | Over-normalization. Status column with audit timestamps provides the same audit trail with simpler queries. |
| Agent auto-link evidence | Agent does not have project scope. All evidence association requires human judgment about relevance to the specific project. |

### 10.10 Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| Polymorphic evidence_id bypasses type safety | Server-side validation queries the correct table per evidence_type before insert. Rejects unknown types at the schema level. |
| Evidence deleted after link created | Link row unchanged (`status` stays `active`). GET query dynamically returns `evidence_status: "gone"` / `unavailable: true` when the evidence row is missing. Link is NOT auto-set to `removed`. |
| Concurrent duplicate creation | Unique constraint catches the race. On IntegrityError: rollback the failed insert, re-query the existing row. If `active` → return 200. If `removed` → apply relink rules (reactivate + evidence_relink audit) → return 200. Never returns 409 for a duplicate race. |
| Audit table growth | Each link create/remove is one OntologyRuntimeAudit row. Acceptable — query runtime audit is write-only (no query API exposed by design, matching existing Phase 14.5 pattern). |
| Migration number collision | Resolved as migration `0024`; upgrade and downgrade were verified on SQLite. |

### S2.2 Delivered

Implementation (6 new files, +1078 lines):

- **Model**: `ProjectEvidenceLink` in `models.py` — 13 columns, polymorphic evidence_id, unique constraint on (project_id, evidence_type, evidence_id), soft-delete via status=removed with removed_by/removed_at audit fields.

- **Migration**: `0024_v24_project_evidence_links` — upgrade/downgrade verified on SQLite.

- **Router**: `src/semantic_lighthouse/routers/evidence_links.py` — 3 endpoints:
  - `POST` (owner/admin): 201 new, 200 active duplicate, 200 relink. Dynamic status codes via FastAPI Response. Idempotency: existing link checked before status validation.
  - `GET` (member+): status_filter, evidence_type, limit/offset with 422 validation. Dual group_id+project_id filtering.
  - `DELETE` (owner/admin): soft-delete with updated_at tracking. Double delete idempotent.

- **Schemas**: `EvidenceLinkCreateRequest`, `EvidenceLinkResponse`, `EvidenceLinkListResponse`, `EvidenceProvenance` in `schemas.py`.

- **Permissions**: `get_membership_or_404` (403 for non-member), `require_group_role` (403 for non-owner/admin). Cross-group/project returns 404.

- **Provenance**: Document (title, status, file_name, safe source_label, created_at) and RAGRun (truncated question, confidence, retrieval_method, citation_count). Never exposes source_path, storage_path, raw_content, answer, snippet, or prompt. Source evidence gone → link stays active, provenance returns unavailable=true.

- **Audit**: Reuses `OntologyRuntimeAudit` with operations `evidence_link`/`evidence_unlink`/`evidence_relink`. `field_names` stores only field name strings, never values.

- **Tests**: 38 targeted tests covering permissions, isolation, evidence status validation, idempotency, lifecycle, audit, provenance minimization, input boundaries, and fail-closed commit behavior.

- **Full regression**: 786 passed, 3 skipped.

Residual boundaries (not in S2.2):
- No UI — evidence links are API-only. Goal stage links remain navigation-only.
- No Agent auto-link — Agent tool registry has zero evidence write tools.
- No conversation/task/AgentRun project scope (deferred to S2.3).

---

## 11. S2.3 Project Work Context

Status: S2.3B delivered and safety-reviewed. Final closeout / next S2 slice selection remains.

### 11.1 Decision

Add nullable, indexed `project_id` foreign keys to `Conversation`, `Task`, and `AgentRun` in migration `0025`. The field is optional and immutable after creation. Existing rows remain unscoped (`NULL`), existing group-scoped API behavior remains valid, and no data is backfilled by inference.

This is a real execution boundary, not a display label. When a Conversation or AgentRun is project-scoped, every knowledge lookup must be limited to ready Documents connected to that project by an active `ProjectEvidenceLink`. An empty project evidence set returns no evidence; it must never fall back to all group documents.

### 11.2 API And Compatibility Contract

- Keep the existing group-scoped routes. Do not add duplicate nested project routes.
- Add optional `project_id` to create requests and responses for conversations, tasks, and Agent runs.
- Add optional exact `project_id` filters to their list endpoints. Omitting the filter preserves current all-scope behavior.
- Validate project membership server-side with `BusinessProject.group_id == route group_id`. Cross-group or unknown projects return 404.
- Reject creation in an archived project with 409. Existing scoped records remain readable, but message sending, Agent execute/respond, and task mutation return 409 after project archival.
- Do not permit project reassignment. There is no PATCH operation for `project_id`.
- Conversations and Agent runs remain private to their creating user. Tasks remain shared within the group under their existing permission rules.

### 11.3 Conversation And Agent Consistency

- Creating an AgentRun with `conversation_id` must validate that the conversation belongs to the route group and current user. This closes the current unchecked-FK integrity gap.
- When `conversation_id` is supplied, the run inherits the conversation's `project_id` server-side. If a non-null `project_id` is also supplied, it must match; a scoped project cannot be combined with an unscoped conversation.
- Project-scoped Conversation retrieval (keyword, semantic, hybrid, auto, and tool-loop searches) receives an allowed Document ID set derived from active project evidence links.
- Project-scoped Agent `search_knowledge_base` and `list_documents` use the same allowed set.
- `archive_document` is unavailable inside a project-scoped Agent run. Archiving a group document is a group-global side effect that can affect other projects; it must be performed from an unscoped run with the existing role and HITL checks.
- The model/client never supplies an authoritative project or document scope to a tool. The server derives it from the persisted AgentRun and ProjectEvidenceLink rows.

### 11.4 Task Source Rules

Unscoped task creation preserves the existing source contract for backward compatibility. A project-scoped task applies stricter source validation:

| source_type | Required project consistency |
|-------------|------------------------------|
| `manual` | Allowed with no external source lookup. |
| `conversation` | Source exists in the same group, is owned by the caller, and has the same `project_id`. |
| `agent_run` | Source exists in the same group, is owned by the caller, and has the same `project_id`. |
| `rag_run` | Source belongs to the group and has an active `ProjectEvidenceLink` to the project. |

Unknown, cross-group, or cross-user source references return 404 to avoid existence leakage. A caller-owned source with a conflicting project context returns 409 only after ownership and group checks pass.

### 11.5 Lifecycle And Non-Goals

- Project archive never cascades, deletes, or rewrites conversations, tasks, Agent runs, messages, steps, or evidence links.
- No project-specific RBAC is introduced; group membership remains the authorization boundary.
- No frontend work, navigation changes, automatic association, historical backfill, Agent-created links, MCP runtime, Graph RAG, or Ontology writes.
- No new audit table is required. Creator/user fields, immutable `project_id`, Task source traceability, Agent steps, and existing HITL records remain the audit surface.

### 11.6 Delivery Slices

**S2.3A — Context persistence and validation (delivered)**

- Migration `0025`, model/schema fields, response serialization, list filters, archived-project write freeze, Agent conversation validation/inheritance, and project-scoped Task source validation.
- Related tests must cover nullable compatibility, cross-group 404, archived 409, immutable context, user privacy, source consistency, and no inferred backfill.

**S2.3B — Project-bounded retrieval and tools (delivered and reviewed)**

- Add an optional server-derived allowed Document ID constraint to keyword, semantic, hybrid, Conversation tool-loop, and Agent document tools.
- Tests must prove project A cannot retrieve/list project B or unlinked documents, empty evidence never falls back group-wide, unscoped behavior is unchanged, and project-scoped archive is denied.

**S2.3C — Final closeout / next-slice decision (Codex)**

- S2.3A and S2.3B safety review is complete. Record final closeout if no more S2.3 work is needed, then choose the next separately scoped S2 slice.
- Prefer focused or grouped verification at phase boundaries. The all-in-one non-E2E command timed out on Windows; grouped suites are more diagnostic and avoid hiding progress.

### 11.7 S2.3A Delivery And Review

- Commit `ed621ef` adds migration `0025`, nullable indexed project context, compatible request/response fields, exact list filters, archived-project write freeze, validated Agent Conversation inheritance, and scoped Task source rules.
- Codex review fixed five boundary defects before acceptance: archived Conversation history remains readable; an unscoped Conversation cannot be combined with a scoped AgentRun or Task; all project list filters validate route-group ownership; RAG evidence checks include `group_id`; Agent detail preserves `project_id`.
- Verification: 26 focused S2.3A tests and 95 related Conversation/Task/Agent tests pass. Changed-file ruff is clean. SQLite migration upgrade, downgrade to 0024, and re-upgrade to 0025 pass.
- Full non-E2E regression was intentionally deferred until S2.3B/S2.3C boundary.

### 11.8 S2.3B Delivery And Review

- Commit `ea216bc` constrains project-scoped retrieval and Agent document tools to server-derived active `ProjectEvidenceLink` Documents. Unscoped retrieval keeps its previous group-wide behavior; scoped empty evidence returns no evidence instead of falling back.
- Codex review fixed three boundary defects before acceptance: semantic Conversation retrieval now receives `allowed_document_ids`; scoped Agent V1 archive requests fail immediately instead of entering confirmation; scoped Agent V2 and legacy scoped HITL archive paths fail the run instead of mutating shared Documents.
- Verification: 16 focused S2.3B tests pass. 100 related retrieval/conversation/Agent/project-context tests pass. Changed-file ruff is clean. A one-shot non-E2E full regression timed out after about 10 minutes with no failure output, so regression was rerun in grouped suites covering all 832 collected non-E2E tests; grouped runs passed.
- Residual boundary: no UI changes. S2.3 only makes project context an execution boundary for backend retrieval/tools.

---

## 12. S2.4 Pilot Surface Consolidation

Status: S2.4 backend consolidation closed after S2.4A/B/C.

### 12.1 Decision

Do not collapse standalone capability pages into Pilot tabs today. Each capability must independently prove it has a complete backend contract before a Pilot surface replacement is designed. Premature navigation hiding breaks existing workflows without providing a working replacement.

The contract review below assesses five capabilities against explicit readiness criteria. Capabilities that meet the contract are candidates for S2.4B (minimal backend slice for Pilot summaries/links). Capabilities that do not meet the contract must retain their standalone pages until backend parity is proven.

### 12.2 Readiness Criteria

A capability is ready for Pilot surface exposure when:

1. **Project scope**: the record has a validated, immutable `project_id` that the server enforces as belonging to the route group.
2. **Retrieval isolation**: project-scoped retrieval uses only active `ProjectEvidenceLink` Documents and never falls back to group scope.
3. **Write freeze**: archived projects reject new creation and mutation for scoped records.
4. **Audit trail**: every state transition produces an audit record or is explicitly documented as write-only.
5. **Identity boundary**: the capability does not leak cross-project or cross-group data through list, detail, or tool execution paths.

### 12.3 Capability Assessment

#### Documents / Knowledge Base → Pilot Evidence

| Criterion | Status | Evidence |
|-----------|--------|----------|
| Project scope | ✅ | `ProjectEvidenceLink` bridges `Document` → `BusinessProject`. Links are validated server-side for group membership, evidence readiness, and project status. |
| Retrieval isolation | ✅ | S2.3B: `project_document_ids()` derives allowed IDs from active links. Keyword, semantic, and hybrid search all respect the constraint. Empty evidence returns no results. |
| Write freeze | ✅ | Archived projects reject new evidence links. Existing links survive archival but provenance marks evidence as unavailable. |
| Audit trail | ✅ | `OntologyRuntimeAudit` records `evidence_link` / `evidence_unlink` / `evidence_relink` operations. |
| Identity boundary | ✅ | Link queries include both `group_id` and `project_id`. Cross-group returns 404. |

**Pilot surface candidate**: A "Project Evidence" summary panel in the Pilot Goal stage showing linked documents with provenance (title, status, source_label). No embedded full Documents page needed.

#### Conversations → Pilot Ask

| Criterion | Status | Evidence |
|-----------|--------|----------|
| Project scope | ✅ | `Conversation.project_id` added in migration 0025. Server validates project belongs to route group. Immutable after creation. |
| Retrieval isolation | ✅ | S2.3B: `send_message` derives `allowed_document_ids` from `conv.project_id`. Initial retrieval, semantic/hybrid/auto, and tool-loop `search_knowledge_base` all respect the constraint. |
| Write freeze | ✅ | Archived projects block message sending (409). Historical messages remain readable. |
| Audit trail | ⚠️ Partial | Conversation messages are persisted but no project-scoped audit row is written per message or tool execution. Existing `created_at`/`user_id` fields are the audit surface. |
| Identity boundary | ✅ | Conversations are user-private. List endpoint filters by `project_id`. Cross-user access returns 403. |

**Pilot surface candidate**: A read-only conversation summary in the Pilot Goal/Model stage showing recent scoped conversations. Creating a new scoped conversation could be a Pilot action, but the full chat UI should remain the standalone page until project-scoped conversation listing is proven.

**Missing for replacement parity**: No Pilot-embedded chat UI exists. The standalone Conversations page must remain accessible until a project-scoped replacement is built and tested.

#### Tasks → Pilot Actions

| Criterion | Status | Evidence |
|-----------|--------|----------|
| Project scope | ✅ | `Task.project_id` added in migration 0025. Server validates project belongs to route group. Immutable after creation. |
| Retrieval isolation | N/A | Tasks do not perform retrieval. |
| Write freeze | ✅ | Archived projects block task creation (409) and mutation (409). Historical tasks remain readable. |
| Audit trail | ⚠️ Partial | Task status changes are recorded via `updated_at` and `created_by` fields. No dedicated project-scoped audit row. |
| Identity boundary | ✅ | Task list filters by `project_id`. Cross-group source references return 404. Project-scoped tasks validate source consistency (conversation/agent_run ownership, RAG run evidence link). |

**Pilot surface candidate**: A "Project Tasks" summary panel listing scoped tasks with status badges. Creating a task scoped to the current Pilot project could be exposed as a secondary action.

**Missing for replacement parity**: No project-scoped task creation UI exists. The standalone Tasks page must remain until this is built. Source validation for project-scoped `rag_run` tasks requires an active `ProjectEvidenceLink`, which is a deliberate gate, not a gap.

#### Agent Runs → Pilot Advanced

| Criterion | Status | Evidence |
|-----------|--------|----------|
| Project scope | ✅ | `AgentRun.project_id` added in migration 0025. Server validates project and conversation consistency. Can inherit `project_id` from scoped conversation. |
| Retrieval isolation | ✅ | S2.3B: `execute_tool` derives `allowed_docs` from `run.project_id`. `search_knowledge_base` and `list_documents` respect the constraint. Scoped `archive_document` is rejected. `_tool_schemas_for_llm` excludes `archive_document` for scoped runs. |
| Write freeze | ✅ | Archived projects block execute (409) and respond (409). Historical runs remain readable and their steps remain visible. |
| Audit trail | ✅ | `AgentStep` records every tool execution with `action_detail` and `observation`. `OntologyRuntimeAudit` records project-scoped operations. |
| Identity boundary | ✅ | Runs are user-private. List endpoint filters by `project_id`. Cross-user access returns 403. Conversation ownership and group membership are validated on creation. |

**Pilot surface candidate**: A "Project Agent Runs" summary panel showing recent scoped runs with status, phase, and step count. Starting a new scoped run could be a Pilot action.

**Missing for replacement parity**: No project-scoped run creation UI exists. Agent tool execution requires user confirmation (HITL) which currently only works through the standalone Agent console. The standalone page must remain until a Pilot-embedded HITL flow is built.

#### RAG Answer (Ask) → Pilot Goal

| Criterion | Status | Evidence |
|-----------|--------|----------|
| Project scope | ✅ | S2.4C added nullable indexed `RagRun.project_id` and `POST /groups/{gid}/projects/{pid}/rag/answer`. Existing group Ask remains `project_id = NULL`. |
| Retrieval isolation | ✅ | Project RAG derives allowed Documents from active `ProjectEvidenceLink` rows and never falls back to group-wide retrieval when project evidence is empty. |
| Write freeze | ✅ | Archived projects reject new project-scoped RAG answers (409). Historical runs remain readable. |
| Audit trail | ✅ | `RagRun` records question, answer, confidence, citations, and retrieval method. |
| Identity boundary | ✅ | `RagRun` is group-scoped. |

**Pilot surface candidate**: Project-bounded Ask panel in the Pilot Goal stage. Frontend work remains separate; the standalone Ask page must remain until a replacement UI proves parity.

**Boundary**: Project-scoped `RagRun.project_id` proves where the answer was generated. `ProjectEvidenceLink` still proves a human intentionally attached the answer as durable project evidence. S2.4C does not auto-create evidence links.

### 12.4 Consolidation State Summary

| Capability | Project-scoped | Retrieval-isolated | Write-frozen | Pilot candidate |
|------------|---------------|-------------------|-------------|-----------------|
| Documents / Evidence | ✅ | ✅ | ✅ | Evidence summary panel |
| Conversations | ✅ | ✅ | ✅ | Scoped conversation list + create |
| Tasks | ✅ | N/A | ✅ | Scoped task list + create |
| Agent Runs | ✅ | ✅ | ✅ | Scoped run list + create |
| RAG Answer (Ask) | ✅ | ✅ | ✅ | Project-bounded Ask panel |

### 12.5 Pages That Must Retain Direct Access

| Page | Reason |
|------|--------|
| Ask (`/ask`) | Project-bounded RAG exists via API, but no Pilot-embedded Ask UI exists yet. The standalone group Ask remains the only current UI and must stay accessible. |
| Conversations (`/groups/{gid}/conversations`) | No Pilot-embedded chat UI exists. The standalone page is the only way to read and send messages. Project-scoped listing via API filter exists but has no UI. |
| Tasks (`/groups/{gid}/tasks`) | No Pilot-embedded task board exists. Project-scoped listing and creation via API exist but have no UI. |
| Agent (`/groups/{gid}/agent`) | No Pilot-embedded HITL flow exists. Agent tool confirmation requires the standalone console. Project-scoped execution works via API but has no UI. |
| Knowledge Base (`/groups/{gid}/documents`) | Document management (upload, archive, import) is a group-level operation that should not be scoped to a single project. The Pilot evidence panel should show linked summaries, not replace document management. |
| Ontology (`/groups/{gid}/ontology`) | Ontology is group-level semantic governance, not project-scoped. The Model stage already links to it. |

**No page is hidden or removed in this review.** The contract assessment is purely a backend readiness checkpoint.

### 12.6 S2.4B Minimal Backend Slice (Delivered)

The smallest code change that advances Pilot surface consolidation without breaking existing workflows:

**`GET /groups/{gid}/projects/{pid}/summary`** — a single new endpoint returning:

- `project`: name, business_goal, stage, status
- `evidence_count`: number of active `ProjectEvidenceLink` rows
- `recent_evidence`: up to 5 linked documents with provenance
- `conversation_count`: number of scoped conversations
- `task_count`: number of scoped tasks (by status)
- `agent_run_count`: number of scoped Agent runs

This endpoint requires **zero new models, zero new migrations, zero new business logic**. It is a read-only aggregation of existing data. It gives the Pilot frontend a single data source for a "Project Overview" panel without embedding any standalone capability.

**Delivery note**:
- Commit `c021d8d` added `GET /groups/{gid}/projects/{pid}/summary`.
- Codex review tightened the endpoint to reuse the existing evidence-link provenance builder, so document and RAGRun evidence summaries preserve the same data-minimization contract as the evidence-link API.
- Response includes project metadata, active evidence count, up to 5 recent active links with safe provenance, scoped Conversation count, scoped Task counts by status, and scoped AgentRun count.
- Verification: `tests/test_projects.py` passed 65 tests; focused ruff passed for `projects.py` and `test_projects.py`.

**Explicitly out of S2.4B scope**:
- No embedded chat, task board, or Agent console
- No navigation changes
- No page hiding
- No new write endpoints
- No project-bounded RAG endpoint

### 12.7 S2.4C+ Candidates

| Slice | Scope |
|-------|-------|
| S2.4C | Delivered: project-bounded RAG endpoint (`POST /groups/{gid}/projects/{pid}/rag/answer`) |
| S2.4D | Deferred candidate: Pilot-embedded task creation design, reusing existing `POST /tasks` with `project_id` |
| S2.4E | Deferred candidate: Pilot-embedded conversation starter design, reusing existing `POST /conversations` with `project_id` |
| S2.4F | Deferred candidate: Navigation evaluation — hide pages only after replacement parity is proven by tests |

### 12.8 S2.4C Project-Bounded RAG Endpoint Design

**Status**: Delivered.

**Decision**: Add a project-scoped RAG answer endpoint:

`POST /groups/{group_id}/projects/{project_id}/rag/answer`

This endpoint should use the existing `RagAnswerRequest` / `RagAnswerResponse` contract, but it must derive retrieval scope from the route project, not from the client body. It searches only ready Documents connected to the project through active `ProjectEvidenceLink` rows with `evidence_type="document"`. If the project has no active linked Documents, retrieval returns no evidence and must not fall back to group-wide RAG.

#### Data Model

Add nullable, indexed `project_id` to `RagRun` via a new migration.

Rules:
- Existing `POST /groups/{gid}/rag/answer` remains group-scoped and persists `project_id = NULL`.
- New project endpoint persists `RagRun.project_id = project_id`.
- Existing RAG run detail remains readable by group members; optional future list filters may use `project_id`.
- Do not infer or backfill project context for historical RAG runs.

#### Retrieval And Persistence

Implementation should refactor the current RAG router so group-scoped and project-scoped answer paths share the same deterministic answer pipeline:

1. Validate membership in `group_id`.
2. For the project endpoint, validate `BusinessProject.id == project_id` and `BusinessProject.group_id == group_id`; cross-group project returns 404.
3. Reject new project-scoped answers if the project is archived (409). Historical project RAG runs remain readable.
4. Derive `allowed_document_ids = project_document_ids(db, group_id, project_id)`.
5. Pass `allowed_document_ids` into keyword, semantic, hybrid, and auto retrieval paths.
6. Persist the run with `project_id`.
7. Return the same response shape as group RAG.

No client-supplied `project_id` is accepted in the request body.

#### Evidence Link Boundary

Do **not** automatically create a `ProjectEvidenceLink` for the new `RagRun`.

Reason: ProjectEvidenceLink represents explicit human association of evidence to a Pilot project. A project-scoped RAG answer is generated inside project context, but whether that answer should become durable project evidence is still a user decision. Future UI may offer "Save this answer as project evidence", which should call the existing evidence-link API deliberately.

Consequences:
- Project-scoped `RagRun.project_id` proves where the answer was generated.
- `ProjectEvidenceLink` still proves which RAG answers were intentionally attached as evidence.
- Existing task rule for `source_type=rag_run` remains unchanged unless a later slice explicitly updates it.

#### Compatibility

Existing group-scoped Ask must remain unchanged:
- No project requirement.
- Same endpoint and response.
- Same group-wide retrieval.
- Existing tests continue to pass.

The new endpoint is an additive project-scoped path only.

#### API Contract

Request:

```json
{
  "question": "Which supplier risks matter for this pilot?",
  "retrieval_method": "hybrid",
  "limit": 5
}
```

Response: same as `RagAnswerResponse`, with `run_id` persisted to a `RagRun` whose `project_id` equals the route project.

Errors:
- Non-member: 403.
- Project not in route group: 404.
- Archived project: 409.
- Empty project evidence: 200 with `status="no_evidence"` persisted and low-confidence no-evidence response.
- Embedding or chat provider failure: preserve existing 502 behavior and failed-run audit semantics, with `project_id` persisted where possible.

#### Out Of Scope For S2.4C

- No frontend changes.
- No navigation/page hiding.
- No automatic evidence linking.
- No task source rule change.
- No Graph RAG.
- No MCP runtime.
- No Agent tool changes.
- No external KB writes.

#### Test Plan

Focused implementation tests should cover:

1. Member can call project RAG and response persists `RagRun.project_id`.
2. Existing group RAG persists `project_id = NULL`.
3. Non-member cannot call project RAG (403).
4. Route-group member querying cross-group project receives 404.
5. Archived project rejects new project RAG (409).
6. Linked project document is retrievable.
7. Unlinked same-group document is not retrievable.
8. Different project linked document is not retrievable.
9. Empty active project evidence returns no-evidence response, never group fallback.
10. Removed evidence link is ignored.
11. Keyword and semantic/hybrid/auto paths all receive the same allowed document constraint.
12. Project RAG does not auto-create `ProjectEvidenceLink`.
13. Existing `GET /rag/runs/{run_id}` remains group-scoped and readable.
14. Optional `GET /rag/runs?project_id=` filter, if implemented, validates route-group project ownership and does not leak cross-group runs.

Suggested implementation lane: **Safety Lane**. Reason: this touches RAG retrieval scope, persistence, group/project isolation, and a migration.

#### Delivery Note

- Migration `0026_v26_rag_run_project_scope` adds nullable indexed `RagRun.project_id` with no historical backfill.
- Existing `POST /groups/{gid}/rag/answer` remains group-scoped and persists `project_id = NULL`.
- New `POST /groups/{gid}/projects/{pid}/rag/answer` validates the route project, rejects archived projects, derives allowed Documents from active project evidence links, and persists `RagRun.project_id`.
- Keyword, semantic, hybrid, and auto retrieval paths all receive the same allowed Document constraint.
- No `ProjectEvidenceLink` is automatically created for project-scoped RAG runs.
- Verification: 48 focused RAG tests passed; 139 related RAG/retrieval/project-evidence/project-context tests passed; migration 0026 upgrade/downgrade/re-upgrade passed on SQLite. A one-shot non-E2E full run timed out after about 10 minutes with no failure output, so non-E2E regression was rerun in grouped suites covering all 851 collected tests: 848 passed, 3 skipped.

### 12.9 S2.4 Closeout Decision

S2.4 backend consolidation is complete enough for the next frontend surface planning pass:

- S2.4A defined the readiness criteria and prevented premature page hiding.
- S2.4B added a read-only project summary endpoint for Pilot overview panels.
- S2.4C added project-bounded RAG with durable `RagRun.project_id`, strict active-evidence retrieval scope, archived-project write freeze, and no automatic evidence linking.

Do not keep expanding the backend merely because more Pilot embedding is possible. Tasks, Conversations, and Agent runs already have project-scoped backend APIs from S2.3, and RAG now has the missing project-scoped answer path. S2.4D/E/F should be reopened only if frontend replacement planning discovers a concrete API gap.

Standalone pages remain accessible. Navigation hiding belongs to a frontend parity pass, not to backend closeout.
