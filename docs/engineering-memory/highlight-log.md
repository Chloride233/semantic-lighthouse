# Highlight Log

## S2.4 Closeout — Backend Surface Is Ready Enough; Do Not Expand By Momentum

- Date: 2026-06-20
- Version: S2.4 closeout
- Type: decision
- What happened: Closed S2.4 backend consolidation after S2.4A contract review, S2.4B project summary endpoint, and S2.4C project-bounded RAG. S2.4D/E/F are deferred candidates, not automatic next work.
- Engineering judgment: The backend now has the contracts needed for Pilot surface planning: project evidence summaries, project-scoped Conversations/Tasks/Agent runs from S2.3, and project-bounded RAG from S2.4C. More backend endpoints should be driven by a concrete frontend replacement gap, not by the feeling that every standalone page needs a new embedded API first.
- Verification: Documentation-only closeout based on the S2.4C baseline: 48 focused RAG tests, 139 related tests, SQLite migration roundtrip, grouped non-E2E regression across 851 collected tests, and full ruff already passed.

## S2.4C — Project-Bounded RAG Is Scoped Run, Not Auto-Linked Evidence

- Date: 2026-06-20
- Version: S2.4C
- Type: implementation
- What happened: Implemented `POST /groups/{gid}/projects/{pid}/rag/answer` with migration `0026` adding nullable `RagRun.project_id`. Project RAG validates the route project, rejects archived projects, derives allowed Documents from active project evidence links, and passes that constraint through keyword, semantic, hybrid, and auto retrieval. Existing group-scoped `/rag/answer` persists `project_id = NULL`.
- Engineering judgment: A project-scoped RAG run proves where an answer was generated; a `ProjectEvidenceLink` proves a human intentionally attached that answer as durable project evidence. Those are different claims. S2.4C therefore does not auto-create evidence links, even though the endpoint is project-scoped.
- Verification: 48 focused RAG tests passed; 139 related RAG/retrieval/project-evidence/project-context tests passed; migration 0026 upgrade/downgrade/re-upgrade passed on SQLite; grouped non-E2E regression covered all 851 collected tests with 848 passed and 3 skipped; full ruff passed.

## S2.4B — Project Summary Endpoint Reuses Provenance Contracts

- Date: 2026-06-20
- Version: S2.4B
- Type: implementation
- What happened: Added `GET /groups/{gid}/projects/{pid}/summary` as a read-only Pilot overview aggregation endpoint. It returns project metadata, active evidence count, up to five recent active evidence links with safe provenance, scoped conversation count, task counts by status, and scoped Agent run count. No new tables, migrations, frontend changes, write paths, or navigation hiding.
- Engineering judgment: Aggregation endpoints must reuse existing safety contracts instead of inventing parallel summaries. The review changed project summary evidence output to call the evidence-link provenance builder, preserving the same exclusion rules for paths, raw content, generated answers, prompts, citation snippets, errors, secrets, and tokens.
- Verification: 65 focused project tests passed; changed-file ruff passed.

## S2.4A — Pilot Surface Consolidation: Backend Contract Before Navigation Change

- Date: 2026-06-20
- Version: S2.4A
- Type: decision
- What happened: Systematic review of five capabilities against five readiness criteria. Evidence, Conversations, and AgentRuns meet all criteria. Tasks meet four (retrieval N/A). RAG Answer meets zero — no project-bounded retrieval exists. Decision: no pages hidden; standalone pages must remain accessible until backend replacement parity is proven by tests.
- Engineering judgment: Navigation consolidation must follow backend readiness. The contract review provides an objective checklist: project scope, retrieval isolation, write freeze, audit trail, identity boundary.

## S2.3 — Project Context Must Constrain Execution, Not Merely Label It

- Date: 2026-06-20
- Version: S2.3B
- Type: decision
- Context: Conversations, Tasks, and Agent runs are group-scoped parallel capabilities. Adding `project_id` could make them legible inside the Pilot chain, but a nullable column alone would falsely imply isolation while retrieval and tools still read the whole group.
- What happened: S2.3A implemented optional, immutable, backward-compatible project context. S2.3B then made that context executable: project-scoped Conversation retrieval and Agent document tools now use only active ProjectEvidenceLink Documents; empty project evidence returns no evidence; unscoped behavior remains group-wide; project-scoped `archive_document` is denied. Review caught and fixed eight boundary gaps across the two slices, including archived history blocking, unscoped source mixing, missing project validation on filters, missing `group_id` on RAG evidence checks, semantic retrieval scope propagation, and scoped archive paths in Agent V1/V2/HITL.
- Engineering judgment: Context labels without execution constraints are dangerous because they create confidence without isolation. The server must derive project scope from persisted rows, propagate it through every retrieval/tool path, preserve old unscoped behavior explicitly, and deny shared-document mutations from scoped Agent runs.
- Verification: S2.3A passed 26 focused and 95 related tests plus SQLite migration upgrade/downgrade/re-upgrade. S2.3B passed 16 focused tests, 100 related tests, changed-file ruff, and grouped non-E2E regression covering all 832 collected non-E2E tests.

## S2.2 — Project Evidence Links: Explicit, Human-Reviewed, Auditable

- Date: 2026-06-20
- Version: S2.2
- Type: decision
- Context: FDE needs to ground business problems in enterprise knowledge. The question: how to associate Documents and RAG runs with a specific Pilot project without auto-linking, without leaking cross-group data, and without letting Agent auto-associate.
- What happened: Single `ProjectEvidenceLink` table with polymorphic evidence_type/evidence_id. Owner/admin create; member read. Active duplicate is idempotent (200, no audit). Removed links can be relinked. Evidence must be ready/success to link. Archived projects block new links but active duplicates survive. Source evidence deletion does NOT auto-remove links — GET dynamically returns unavailable=true. 38 targeted tests, 786 full regression. Audit via existing OntologyRuntimeAudit.
- Engineering judgment: Evidence association must be explicit (user action, not auto-link), project-scoped (not just group-scoped), revocable (soft-delete), and auditable (every transition recorded). Agent must not auto-link evidence. The key decision was the single-table polymorphic design over multi-table join tables — all evidence types share identical lifecycle, so a type discriminator is simpler.

## Frontend F2C — Responsive, Accessible, Visually-Polished Guided Pilot Workspace

- Date: 2026-06-20
- Version: F2C
- Type: polish
- Context: F2B delivered the full guided pilot closed-loop. F2C was the final polish pass — responsive at all breakpoints (1440/1024/768/390), accessibility (WCAG AA touchpoints), and visual cleanup — without adding features or modifying backend.
- What happened: CSS fixes targeted the root causes of layout drift: checkbox/radio now use stable native sizing (not inheriting full-width `input` rules), group select constrained to 180px max-width, stage rail adapts direction at 600px (horizontal→vertical), long text uses `word-break: break-all` + `overflow-wrap: anywhere`, tables scroll within containers only. Dialog received full accessibility treatment: `aria-modal`, `aria-labelledby`, focus trap (Tab wraps within), Escape/overlay/cancel cleanup, `role="alert"` on errors. More tools dropdown gained keyboard nav (Enter/Space/ArrowDown to open, Arrow keys to navigate, Escape to close) with `aria-controls` + `aria-labelledby`. Profile/contract table `<th>` now use `scope="col"`. All form controls have associated `<label>`. `focus-visible` uses 2px solid outline with offset. Screenshot script completely rewritten: menu is closed, page scrolled to top, stage-specific elements waited for (.draftRow for model, .stagePanel for validate, .queryForm for pilot), mobile runs its own independent pipeline, programmatic overflow checks (`scrollWidth ≤ innerWidth`).
- Engineering judgment: Visual polish without feature creep. The key discipline was resisting the temptation to "improve" the UI — all old pages remain in "更多工具" dropdown, no gradients or glass effects were added, no card-in-card patterns introduced. Each stage has one primary action with clear secondary/danger hierarchy. The responsive fixes were done at the CSS selector level (not with per-element inline styles) to maintain consistency. Accessibility fixes were surgical — aria attributes on existing elements, focus management in existing handlers, keyboard nav added to existing dropdown pattern.
- Verification: E2E expanded to 18 tests (5 new F2C: responsive no-overflow, dialog focus trap+Escape, more tools keyboard nav, table th scope, form labels). verify_ui 47/47 preserved. Screenshots at `.tmp/f2c/` — 6 files, stage-verified, 0 console errors. No backend, migration, or API changes.

## Frontend F2B — Guided Pilot Full Closed-Loop Acceptance Verified

- Date: 2026-06-20
- Version: F2B
- Type: acceptance
- Context: F2B is the second frontend slice of Phase 14, turning the model → validate → pilot stages into a real clickable guided workflow. The question was whether the full owner closed-loop (generate drafts → batch accept → build package → generate bindings → activate → query) works end-to-end, whether real member join-by-invite works, whether WARN/FAIL quality gates are correctly enforced, and whether project isolation holds.
- What happened: verify_ui expanded from 35 to 47 checks including a real owner full chain with assertions on Alice data, provenance, no storage_path, and stage persistence. E2E tests expanded from 8 to 13 with five new F2B tests: owner full closed-loop, real member via invite (not outsider), WARN/FAIL workflow with Playwright route mocking, project A/B isolation, and code quality checks. No backend, migration, or API changes were needed. All ruff errors fixed (41→0). Six screenshots generated at desktop 1280px and mobile 390px (33–86 KB, 0 console errors).
- Engineering judgment: The real member test was the critical gap — the previous test claimed to test a member but actually tested an outsider. Fixing it required creating an invite via API and joining through the UI. The WARN/FAIL test uses Playwright route mocking to simulate quality gate status, proving that FAIL blocks the build button and WARN requires explicit reason + captures allow_warnings/override_reason. Project isolation is verified by creating two projects in the same group and asserting no draft/binding name leakage. verify_ui now does real clicks through the full pipeline, not just page-existence checks.
- Verification: verify_ui 47/47 PASS, backend pytest 749 passed, ruff clean, 6 screenshots valid, git diff --check clean. Documentation aligned: F2B marked delivered, roadmap metrics updated (434→749, 0017→0023), Kimi/outdated frontend-ban text removed.

## Phase 14.5 — UModel 研读核验：借鉴模型/存储解耦、拒绝 SPL/MCP Runtime、定位 Evidence-grounded Ontology Compiler

- Date: 2026-06-20
- Version: Phase 14.5
- Type: decision
- Context: 在实现 Pilot Read Runtime 之前，系统研读了 UModel 的公开文章和设计理念，核验哪些理念值得借鉴、哪些能力被文章夸大、Semantic Lighthouse 的差异化创新应该在哪里。
- What happened: 经过对比核验，确认六项值得借鉴的架构决策：(1) 模型定义与运行时分离 — Object Type/Property 定义在 contract package 中，数据绑定和查询是独立 runtime；(2) Dataset 作为语义描述，物理数据由独立绑定负责 — DatasetAsset 存储 profile 元数据，OntologyDatasetBinding 显式连接 contract → file；(3) Entity/Object 字段与数据列之间使用显式映射 — property_mappings 记录 property api_name → column name；(4) Query Service 作为 REST、UI、Agent、未来 MCP 共用的唯一读取边界 — `/runtime/query` 是所有读取路径的唯一入口；(5) Agent/MCP 复用服务层，不直接访问底层存储 — 已在 Agent 工具注册和 MCP 边界设计中体现；(6) MCP 写能力默认关闭 — `docs/mcp-agent-boundary-design.md` 已明确此边界。
- 同时确认七项不照搬的决定：(1) 不实现自定义 SPL/DSL — 我们的 query 只接受 JSON equality filters；(2) 不实现通用 AST 或查询优化器 — 直接顺序读取 CSV/XLSX 行；(3) 不采用仅生成外部执行计划的 plan-only 架构 — 我们直接读写文件；(4) 不实现通用自动 Schema Discovery — 我们的 profiling 是 metadata-first，不扫描全库；(5) 不实现时间旅行或通用 temporal engine；(6) 不实现 MCP runtime、Graph RAG 或 Ontology 写入；(7) 不把文章中未经官方仓库证明的能力写成 UModel 当前已实现事实。
- Semantic Lighthouse 的创新定位明确为：「Evidence-grounded Ontology Compiler：把企业文档和数据编译成有证据、可审核、可查询、可供 Agent 安全使用的语义运行时。」这个定位准确区分了三层能力：(a) 当前已交付 — contract compilation + binding + query + provenance + activation；(b) 产品方向 — Agent/MCP adapter 复用 query service，不作独立 runtime；(c) 不写入简历 — 未实现的 MCP、Graph RAG、时间旅行、SPL。
- Engineering judgment: 追赶参考项目不是目标。UModel 的公开文章对模型/存储解耦和统一查询边界有很好的阐述，但文章将许多规划中的能力写成了当前状态。Semantic Lighthouse 的差异化在于：(1) 每个 contract property 都有明确的证据链（哪个数据集、哪个列、哪个 profile），不是自动推断；(2) 查询结果带有完整的 provenance block（package id/content_hash、dataset id/content_hash），随时可审计；(3) 类型转换是确定性的且报错不静默伪造；(4) 整个链路从 document/data → draft → human review → package → binding → query → provenance 每一步都有显式记录和权限门禁。这些特性在 UModel 文章中未出现。
- Verification: Phase 14.5 全部 56 测试通过，216 个 Phase 14 测试零回归。本次核验结论已同步到路线、工程记忆和求职叙事。没有为了追赶参考项目引入 SPL、MCP runtime 或通用数据平台。
- Interview version: 我研究了 UModel 的设计理念，采纳了模型/存储解耦和统一查询 Service 边界的思路，但明确拒绝引入自定义查询语言、通用优化器和 MCP runtime。Semantic Lighthouse 的查询是确定性的、有证据可审计的、权限隔离的 — 不是为了"更强大"，而是为了"更可信"。

## Phase 14.3 — Dataset Profile Becomes Deterministic, Human-Reviewable Contract Proposals (Not Auto-Published Ontology)

- Date: 2026-06-19
- Version: Phase 14.3
- Type: decision
- Context: Phase 14.2 delivered metadata-first dataset profiling with PK/FK detection. The next step was bridging those profiles into the existing business_v1 Ontology Modeling Draft chain without introducing LLM-driven auto-modeling, without auto-publishing contracts, and without bypassing the Phase 11.4 human review gate.
- What happened: Added `project_id` and `source_dataset_id` to the `OntologyModelingDraft` model (migration `0020`). Built a deterministic, pure-Python service (`dataset_modeling.py`) that converts column profiles into proposed Object Types (with best PK selection by confidence/position), Properties (type-mapped, required=not nullable), and Link Types (from project-local FK suggestions, many_to_one). Never generates Action Types — format data alone cannot infer safe business actions. Every draft carries `contract_profile=business_v1`, `generator=dataset_deterministic_v1`, and structured generation keys for idempotency. Evidence refs include dataset identity + column metadata but never sample values, raw rows, or storage paths. Stage advances `data → model` only on successful generation; accepted/rejected drafts are never overwritten.
- Engineering judgment: The bridge from raw data profiles to modeling drafts is a correctness-critical path. Doing it deterministically with visible rules (PK selection, type mapping, FK naming conventions) is the right foundation. Future AI can enhance display names and descriptions but must not substitute for the deterministic PK/FK evidence chain. The explicit decision to NOT generate Action Types from data acknowledges that business actions require domain context that column statistics alone cannot provide. Keeping human review as the mandatory gate (via the existing Phase 11.4 single/batch accept/reject workflow) ensures that automated proposals do not drift into automated publishing.
- Verification: 125 combined tests (26 drafts + 34 review + 38 contract + 27 modeling) passed with zero legacy regressions. Migration upgrade/downgrade cycle verified on SQLite.

## Phase 14.1 — Product Shifts from Parallel Features to Business Pilot Main Chain

- Date: 2026-06-19
- Version: Phase 14.1
- Type: decision
- Context: Phases 1–13 delivered a rich set of parallel capabilities (RAG, Agent, Ontology drafts/packages/contracts, tasks, conversations). The product risk was becoming a collection of features without a guided user path. Phase 14 introduces business pilot projects as the organizing main chain: each group workspace contains projects that follow a fixed five-stage pipeline (goal → data → model → validate → pilot).
- What happened: Added `BusinessProject` model (migration `0018`), five REST endpoints under `/groups/{gid}/projects`, a deterministic stage progression helper, and 57 permission-isolated tests. Stage is backend-controlled — clients cannot skip, reverse, or directly set it. Old features (RAG, Agent, Ontology, tasks) are intentionally NOT removed — they remain parallel capabilities accessible from the workspace, but the product narrative now centers on the pilot project chain.
- Engineering judgment: A product that only accumulates features eventually loses its story. Phase 14.1 does not delete anything — it adds a spine. The five-stage chain gives every feature a place: RAG informs the goal stage, data profiling informs the data stage, Ontology modeling informs the model stage, quality gates inform the validate stage, and Agent/task workflows inform the pilot stage. The old features are now supporting cast for the business pilot main chain, not the product's identity.
- Verification: 57 tests, ruff clean, migration 0018 at head, git diff --check clean.

## Phase 13 Complete — Business_v1 Backend Contract Is Stable; Frontend Handoff Surface Defined

- Date: 2026-06-19
- Version: Phase 13.6 (review closeout)
- Type: decision
- Context: Phase 13 delivered six slices (profile spec, deterministic validator, compiler with semantic_hash, read-only export API, manufacturing pilot, and review). The question was whether the backend contract surface is stable enough to hand to Kimi for frontend refactor.
- What happened: Full non-E2E regression: 495 passed, 0 failed, ruff clean. All 12 review gates PASS: validator determinism, hash stability (same business = same semantic_hash, different business = different hash), knowledge_meta rejection via contract_profile_mismatch, member/outsider/cross-group isolation, provenance audit chain, no audit noise in compiled manifest, no mutation on GET, manufacturing pilot reproducibility (semantic_hash identical across databases). One minor fix applied: `parameters: None` double-reporting in validator. No new tables, migrations, dependencies, or frontend changes.
- Engineering judgment: The correct posture at a phase boundary is to verify every gate and record what was proved vs what was deliberately not proved. Phase 13 proved the business_v1 contract pipeline is deterministic, stable, and permission-bounded. It did not prove object runtime, SDK generation, MCP integration, or Action execution — and should not claim those. The decision to hand the stable contract surface to Kimi for frontend refactor while keeping CC backend-only is the right sequencing: the typed contract model is now the data contract between backend and frontend.
- Verification: 495 non-E2E tests (434 baseline + 61 Phase 13), ruff clean src/tests/scripts, manufacturing pilot reproducible on fresh DB with identical semantic_hash.

## Phase 13.4 — Contract Export API Reuses Deterministic Compiler with Server-Side Group Isolation

- Date: 2026-06-19
- Version: Phase 13.4
- Type: decision
- Context: After delivering the deterministic validator (13.2) and compiler (13.3), the contract export API needed to expose compiled business manifests without duplicating validation/compilation logic and without weakening group isolation.
- What happened: `GET /groups/{gid}/ontology/packages/{pid}/contract` directly calls `compile_business_contract(pkg)` — no copy-paste of validator or compiler logic into the router. The existing `get_membership_or_404` enforces member+ access; the existing `package_id + group_id` dual-constraint query prevents cross-group access (404). `BusinessContractCompilationError` is caught and mapped to 422 with the full structured `validation_result`. No new tables, migrations, dependencies, persistence, or write paths. The endpoint is strictly Read — POST/PATCH/DELETE return 405.
- Engineering judgment: An export endpoint should be a thin permission-gated wrapper around a deterministic service — not a reimplementation of business logic. The compiler's `BusinessContractCompilationError` is the single truth for what blocks contract exposure; catching it at the API layer and returning 422 preserves that truth without leaking internal exceptions. Dual-constraint queries (package_id + group_id) are the established project pattern for cross-group isolation — no new security mechanism needed.
- Verification: 8 API tests covering member 200, outsider 403, cross-group 404, contract_profile_mismatch 422, invalid package 422, hash stability, no-mutate, and method restrictions. Combined 61 tests (38 validator + 7 compiler + 8 new api + 8 existing package api). Ruff clean.

## Phase 11.4 — Automation Can Only Propose; Accepted/Rejected Must Be Owner/Admin Human Decisions

- Date: 2026-06-19
- Version: Phase 11.4
- Type: decision
- Context: Phase 11.3 delivered deterministic draft generation. The next step was a human review workflow for explicit, auditable accepted/rejected decisions — without Agent review, auto-publishing, or backdoor state modifications.
- What happened: Added single (`POST /drafts/{draft_id}/review`) and batch (`POST /drafts/review-batch`) review endpoints. Owner/admin only. Status transitions are one-way and final: `proposed → accepted` or `proposed → rejected`. Re-review returns 409 — first reviewer metadata never overwritten. Batch is all-or-nothing atomic: any missing/cross-group/already-reviewed draft fails the entire batch with zero partial updates. Rejected requires non-empty review_note (Pydantic model_validator). Generated and manual drafts both reviewable. Review never modifies payload, evidence_refs, created_by, created_at, or source pointers.
- Engineering judgment: Automation proposes, humans decide, audit records preserve the decision. "accepted" does NOT mean "published to production" — it only means a human reviewer confirmed the proposal is worth keeping. Making review one-way and immutable prevents audit trail contamination. The batch atomicity guarantee prevents silent partial state corruption. The rejected-note requirement prevents lazy rejections without explanation. These are the correct enterprise governance posture decisions at this stage.
- Verification: 33 new tests. 365/369 full suite pass (4 pre-existing Playwright E2E). Ruff clean. No new migration. No UI, no Agent, no publishing, no external KB modification.

## Phase 11.3 — Automation Generates Explainable Proposals, Not Autonomous Decisions

- Date: 2026-06-19
- Version: Phase 11.3
- Type: decision
- Context: Phase 11.1+11.2 established the modeling draft read model. The next step was generating Object Type / Property / Link Type / Action Type drafts from governed entities — without LLM hallucination, Agent auto-write, or manual curation of every proposal.
- What happened: Built `generate_modeling_drafts()` — a deterministic service that reads group-scoped entities, relations, frontmatter, and confirmed governance issues, then produces idempotent modeling drafts with stable generation keys. Entity types become Object Type candidates. Frontmatter fields become Property candidates. Resolved wikilink relations become Link Type candidates. Confirmed governance issues become Action Type candidates (using the same `determine_action_type` mapping from Phase 10 curation, now moved to a proper service module). Two-layer dedup (generation_key + type/name) prevents duplicates. Manual drafts are never overwritten. No LLM, no Agent, no filesystem, no external KB.
- Engineering judgment: The right role for automation in enterprise ontology governance is generating explainable, auditable, human-reviewable proposals — not accepting, executing, or publishing. Each generated draft carries a clear description stating it is NOT a production artifact. The generation is fully deterministic: same inputs produce same outputs, every time. The human remains the only path from "proposed" to "accepted" (Phase 11.4). This is the correct posture: automation reduces mechanical curation work while preserving human governance authority.
- Verification: 25 new tests (permissions + all draft types + idempotency + manual protection + evidence scoping). 332/336 full suite pass (4 pre-existing E2E). Ruff clean. Git diff clean. 127 related ontology tests pass. `determine_action_type` move verified — 35 curation demo tests unaffected.

## Phase 11.1+11.2 — Modeling Drafts Start as App-Internal, Group-Scoped Proposals, Not a Full Modeler

- Date: 2026-06-19
- Version: Phase 11.1 + 11.2
- Type: decision
- Context: Phase 10 turned governance issues into a curation pipeline. The next step toward the Ontology semantic operating layer is making governed entities inform structured modeling proposals — without Graph RAG, a full modeling studio, or Agent auto-write.
- What happened: Added `OntologyModelingDraft` as an app-internal, group-scoped, audit-trailed read model (`ontology_modeling_drafts`, migration `0016`). Each draft carries a `draft_type` (object_type/property/link_type/action_type), evidence linkage to source entities/relations/issues/RAG runs, and a status lifecycle (proposed → accepted/rejected in Phase 11.4). API: `POST /groups/{gid}/ontology/drafts` (owner/admin create proposed) and `GET /groups/{gid}/ontology/drafts` (member+ read with filters). All source evidence IDs are validated against group membership — cross-group references return 404 without leaking existence. 16 tests cover permissions, isolation, evidence linkage, and filter behavior.
- Engineering judgment: The right first step for modeling drafts is a simple read model with group-scoped evidence pointers — not a generation engine, not a review workflow, and not a UI. Phase 11.1+11.2 establishes the data model, permission boundary, and evidence validation before any automation. Drafts are app-internal proposals only; they are never written back to the external KB. The absence of unique constraints and complex dedup logic keeps the schema open for future generation patterns without premature locking. Status always defaults to `proposed` on create — accepted/rejected will be added by the human review workflow in 11.4.
- Verification: 297 pytest passed (4 pre-existing E2E failures), ruff clean, migration 0016 at head, git diff --check clean.

## Phase 10 Complete — Governance Pipeline Operational, Phase 11 Modeling Drafts Next

- Date: 2026-06-18
- Version: Phase 10.5 (review complete)
- Type: decision
- Context: Phase 10 governance operations delivered. The next step toward the Ontology semantic operating layer is making governed entities inform structured modeling proposals.
- What happened: Phase 10 turned the Phase 9 read model into an operational governance pipeline: deterministic issue triage, curation backlog aggregation, graph scope/status controls with tooltips, and a read-only evidence-to-entity navigation bridge. Phase 10.5 review verified the full chain (76 tests pass, ruff clean, demo reproducible). Phase 11 is planned as Ontology Modeling Drafts v1 — see `docs/phase11-planning.md`.
- Engineering judgment: After governance operations are reliable, the next increment is letting humans review structured modeling proposals derived from governed entities — without Graph RAG, a full modeling studio, or Agent auto-write. Phase 11 drafts are app-internal, group-scoped, audit-trailed proposals (proposed/accepted/rejected), not production schema. The deterministic generation path avoids LLM noise. Agent may read/propose, never auto-create/accept/publish.
- Verification: `docs/phase11-planning.md` created with task slices, non-goals, guardrails. All entry docs sync'd: roadmap Phase 8/9/10 headers fixed, handoff sequencing updated, PRD/README/PRODUCT reflect Phase 10 complete, Phase 11 planning.

## Phase 10.4 — Evidence-to-Ontology Bridge Links RAG Citations to Entities Without Graph RAG

- Date: 2026-06-18
- Version: Phase 10.4
- Type: highlight
- Context: RAG answers showed citations with document titles and snippets, but there was no path from a citation to its corresponding ontology entity. Tasks sourced from RAG runs had the same gap. Phase 10.1–10.3 built the ontology governance pipeline; Phase 10.4 needed to close the loop by making RAG evidence traceable to governed entities.
- What happened: Created `ontology-links.js` with a cached entity index (`byDocumentId` + `bySourcePath` Maps) and a `findEntityForCitation()` matcher. Updated `answerCard` to accept an optional `ontologyIndex` and render `🔗 <entity_title>` pill badges on matched citations linking to `#/groups/{gid}/ontology?entity_id={id}`. Updated `ask.js`, `rag.js`, and `tasks.js` to load the index and pass it through. Added ontology page `?entity_id=` deep link support.
- Engineering judgment: This is a read-only bridge — it links existing data without changing the retrieval algorithm, adding a graph database, or introducing Graph RAG. The citation→entity link is purely navigational: it tells the user "this citation maps to this governed entity" and lets them navigate to verify. This is the correct enterprise governance posture: evidence is traceable to governed entities, but the retrieval pipeline remains deterministic and the ontology read model has no write-back path from RAG. The `ontologyIndex` opt pattern ensures backward compatibility — old `answerCard` callers are unaffected.
- Verification: All JS valid (node --check), ruff clean, git diff --check clean. 1 new file + 7 modified. verify_ui adds ontology deep-link crash check.

## Phase 10.3 — Graph UX Polish Improves Operability Without Crossing the Graph Runtime Boundary

- Date: 2026-06-18
- Version: Phase 10.3
- Type: highlight
- Context: Phase 9.5 delivered a basic SVG graph. Phase 10.1–10.2 operationalized governance issues into a curation backlog. The graph UX needed polish to make it a usable governance tool without introducing a graph database, layout library, or modeling capabilities.
- What happened: Added graph scope controls (selected/visible/all), relation status filter (all/resolved/unresolved), a color legend, SVG `<title>` tooltips on nodes and edges, selected node highlighting, an unresolved targets list (amber box, no fake entities), clickable entity detail relation targets for navigation, and issue triage/code filters. All filtering is frontend-only — zero API changes. Mobile layout collapses controls vertically at 760px.
- Engineering judgment: The right next step after operationalizing issues was making the read model more usable for governance operators. Every UX addition stays within the read-only SVG boundary: no graph library (d3, vis.js), no graph database (Neo4j), no Graph RAG, no modeling studio, and no Agent auto-write. The unresolved targets list is especially important — it surfaces broken links without fabricating phantom entities, which is the correct enterprise governance posture. The `<title>` tooltip approach uses native SVG, avoiding JS tooltip libraries and keeping the implementation lean.
- Verification: JS syntax valid (`node --check`), ruff clean, git diff --check clean. 3 files changed (+2 verify_ui checks for graph controls and issue filters).

## Phase 10.1/10.2 — Governance Issue Triage Turns Scan Findings into Human Curation Backlog

- Date: 2026-06-18
- Version: Phase 10.1 + 10.2
- Type: highlight
- Context: Phase 9 surfaced 97 governance issues from the real KB — but without triage or actionable next steps, they were just a list. Phase 10 needed to operationalize them into a curation workflow.
- What happened: Phase 10.1 added `triage_status` (pending/confirmed/ignored), `triaged_by`, `triaged_at`, `triage_note`, and stable `issue_key` fields. Triage state persists across rescans via issue_key matching. Phase 10.2 built `scripts/run_ontology_curation_demo.py` — a deterministic rule-based triage (NOT LLM-driven) that classifies all 97 issues into actionable categories and aggregates them into 39 curation backlog entries. The backlog is human action guidance only — no automated KB fix.
- Engineering judgment: The governance pipeline is now operational: scan → issue detection → deterministic triage → curation backlog → human curator action. This proves that governance issues can be systematically managed without LLM, Graph RAG, modeling studio, or Agent auto-write. The backlog is a prioritized work queue for a human knowledge curator, not an automated pipeline. This is the right level of automation for enterprise ontology governance — surface, classify, prioritize, suggest, but never auto-modify the knowledge base.
- Verification: 76/76 tests (35 curation demo + 41 ontology), ruff clean, rescan persistence confirmed (97/97 triage preserved), `docs/ontology-curation-demo-report.md` generated.

## Phase 9.5 — Ontology Graph UI as Read Model Visibility, Not Graph Database

- Date: 2026-06-18
- Version: Phase 9.5
- Type: highlight
- Context: Phase 9.1–9.4 had entities, relations, and governance issues in the API. The final Phase 9 step was making that visible.
- What happened: Built `static/js/pages/ontology.js` — a three-column read-only governance console. Entity list with type/status/q filters, SVG graph with color-coded per-type nodes (resolved=实线, unresolved=虚线), entity detail panel with inbound/outbound relations and linked issues, and a governance issue list grouped by severity. Owner/admin can trigger scan; member sees read-only view. All backed by existing group-scoped REST APIs.
- Engineering judgment: The Ontology graph UI is read model visibility — it renders what the scan produces. No graph database, no layout library, no modeling studio, no Agent auto-write. The SVG layout is deterministic circular for up to ~40 related nodes. This proves the governance pipeline (scan → entities → relations → issues → visible) without introducing a graph runtime.
- Verification: 36/36 ontology tests, verify_ui Ontology page renders PASS, ruff clean.

## Phase 9.3 — Wikilink Relations as Read Model, Not Graph Database

- Date: 2026-06-18
- Version: Phase 9.3
- Type: highlight
- Context: Phase 9.1+9.2 had entities and validation issues. The next natural step was connecting entities.
- What happened: Added `OntologyRelation` read model with wikilink extraction from `Document.raw_content`. Parses `[[target]]`, `[[target|label]]`, `[[target#anchor]]`, and relative paths. Results in resolved (target entity found) or unresolved (missing) relations. Relations are rebuilt on each scan, idempotent via unique constraint.
- Engineering judgment: Relations form a read-only link graph between entities without introducing a graph database (Neo4j, etc.) or Graph RAG. Unresolved relations are candidate governance issues for Phase 9.4 — they are not dropped silently. The `upload:` prefix handling is a pragmatic normalization, not a leak.
- Verification: 25/25 ontology tests (10 new relation tests), 234 full suite, ruff clean, migration 0013 at head.

## Phase 9 Ontology Core v1 — Governance First, Read-Only, Not Graph RAG

- Date: 2026-06-18
- Version: Phase 9.1 + 9.2
- Type: highlight
- Context: Phase 8 had completed the demo loop. The project was ready to start the Ontology product path. Risk: jumping to a modeling studio, Graph RAG, or Agent auto-writes before the existing KB was governable.
- What happened: Delivered `OntologyEntity` and `OntologyValidationIssue` read models, `0012` migration, `services/ontology.py` scan engine, `POST /ontology/scan` + `GET /ontology/entities` + `GET /ontology/issues` API, and 15 ontology tests. Scan validates Document.frontmatter against schema.md controlled vocabularies with type conflict detection. API is group-scoped, scan is owner/admin-only.
- Engineering judgment: The first Ontology step should be read-only governance — making the KB governable as entities, relationships, and issues — not a modeling studio, Graph RAG, or Agent auto-write. Phase 9 is sequenced: 9.1 validation + 9.2 entity extraction → 9.3 wikilink relations → 9.4 issue list → 9.5 graph UI.
- Risk if ignored: Starting with rich UI or Graph RAG would force heavy design before measuring KB quality. Validation read model surfaces real drift without modifying external KB.
- Verification: 15/15 ontology tests, 224 full suite, ruff clean, migration `0012` at head.
- Interview version: I started the Ontology path with read-only governance, not Graph RAG. The scan engine validates every document's frontmatter, extracts entities, and flags issues — all group-scoped and permission-aware.

## Product North Star Re-centered On Ontology Semantic Operating Layer

- Date: 2026-06-18
- Version: Product Alignment v2
- Type: decision
- Context: The project had strong trusted RAG, task, and controlled Agent foundations, but the entry documents still described the destination mostly as a knowledge evidence workspace. That could steer new sessions toward generic RAG/Agent work instead of the user's intended Ontology direction.
- What happened: Updated `AGENTS.md`, `PRODUCT.md`, `docs/product-alignment-prd.md`, `CLAUDE.md`, `README.md`, `docs/project-roadmap.md`, and `docs/agent-handoff.md` around one north star: Semantic Lighthouse helps enterprises turn fragmented knowledge, documents, systems, and workflows into a permission-aware, auditable, actionable Ontology semantic operating layer. Phase 8 remains the demonstrable RAG -> task -> Agent/HITL -> audit loop. Phase 9 starts with Ontology Core v1 governance and graph visibility.
- Engineering judgment: The project should not skip from trusted RAG directly into a full modeling studio, Graph RAG, or Agent auto-write path. The safer first Ontology step is read-only governance: schema/frontmatter validation, entity extraction, wikilink relation extraction, broken-link detection, ontology graph, and entity detail.
- Risk if ignored: Future sessions could keep adding RAG or Agent features without moving toward the semantic operating layer, or they could overcorrect by building heavy ontology modeling before the existing KB is governable.
- Fix or control: Entry-point docs now define Ontology as business objects, properties, relationships, actions, permissions, evidence, and Agent-facing interfaces. Handoff records known KB drift, including missing `research/` directory references, stale eval gold IDs, and the absent `docs/kgov-v1-report.md` reference.
- Verification: Documentation-only Fast Lane change; verified with `git diff --check`, `git status --short`, and `rg` alignment scans.
- Interview version: I re-centered the project from "RAG plus Agent" to a staged Ontology product. The current RAG/action loop proves evidence and audit discipline; the next phase turns the knowledge base into governed entities and relationships before attempting Graph RAG or autonomous ontology writes.

## Agent Audit Hardening — Deterministic Safety Trumps Agent Autonomy

- Date: 2026-06-18
- Version: Agent Audit Hardening (post-V2.3)
- Type: highlight
- Context: Three audit gaps found during V2.3 review — Agent archive_document bypassed document audit fields, HITL user confirm/reject overwrote system confirmation records, and production defaults were insecure.
- What happened: (1) Extracted `services/document_lifecycle.py` — a shared `archive_document()` that both the REST endpoint and Agent tool path must go through. Agent can no longer hand-write `doc.status = "archived"`. (2) `respond_to_agent` now appends separate user response steps instead of mutating the original `ask_user` step. Every confirm/reject is an auditable event with `user_id`, `response`, timestamp, and tool context. (3) `Settings.validate_runtime_safety()` fails closed in production — checks JWT_SECRET_KEY not default, ≥32 chars, COOKIE_SECURE=true, DATABASE_URL not default dev connection.
- Engineering judgment: Agent tools must not bypass deterministic backend audit fields. User confirmation itself is an auditable event, not a mutation of the system's confirmation request. Production defaults must fail closed — a missing env var in production should block startup, not silently accept dev credentials.
- Verification: 11 new tests (6 audit, 6 config minus duplicate). Full suite 207 passed, ruff clean.

## Agent V2.3 — Real LLM Validation Is About Boundaries, Not Expansion

- Date: 2026-06-18
- Version: Agent Capability V2.3
- Type: highlight
- Context: V2.2 delivered DeepSeek agent_decide + audit hardening. The next step was to validate that the Agent loop works against real DeepSeek without silently expanding its privileges.
- What happened: (1) Fake-provider eval: 5 scenarios (finalize, list_documents, archived exclusion, risky confirmation, invalid tool) covering tool choice, permission boundary, audit completeness, and unsafe action blocking. All CI-safe, no API key needed. (2) Real DeepSeek smoke: `scripts/smoke_agent_deepseek.py` — 3 short calls validating AgentDecision JSON shape (finalize, call_tool, ChatError). SKIP without key. (3) Smoke scope is intentionally narrow: validates LLM output structure, not AgentRun lifecycle. The lifecycle (ChatError → 502, failed step, fail_run) is covered by pytest route-level fake provider tests.
- Engineering judgment: Real LLM validation is not about "can the Agent do more things." It's about "does the Agent stay within its boundaries when connected to a real model." The 5 eval scenarios verify permission_respected (archived docs excluded), unsafe_action_blocked (risky → confirmation), and tool_choice_correct (invalid tool → error, not silent ignore). No new Agent capabilities were added.
- Risk if ignored: Without eval scenarios, every real LLM interaction would be subjectively judged. Without the smoke script, the project cannot verify that DeepSeek returns a legal AgentDecision without launching a full server.
- Verification: 39 agent + chat + eval tests, ruff clean. Smoke script SKIP (exit 0) without key.

## Agent V2.2 Real Provider And Audit Hardening

- Date: 2026-06-18
- Version: Agent Capability V2.2
- Type: highlight
- Context: V2.1 had a working agent_loop but only with FakeLoopChatClient. The loop needed real LLM decisions, audit recording, and a configurable safety valve before it could be considered a real provider integration.
- What happened: (1) Implemented `DeepSeekChatClient.agent_decide()` using the existing `/chat/completions` path with `response_format: json_object`. Validates tool_name (non-empty) and tool_arguments (must be dict) — LLM output never flows directly into tool execution without type checks. (2) ChatError during agent_loop now writes a failed step + fail_runs the run + returns HTTP 502 — no Agent run left stuck in `executing`. (3) `raw_response` truncated to 500 chars, stored in action_detail. (4) `plan_json` records per-step llm_decision events and stopped events. (5) `Settings.agent_max_steps` (env AGENT_MAX_STEPS, cap 1–10) replaces hardcoded 5. (6) Risky action_detail enhanced with `requires_confirmation`, `risk_level`, `confirmation_reason`.
- Engineering judgment: Did not introduce LangGraph runtime despite evaluating Deep Agents patterns. Absorbed the useful patterns (planning/plan_json, HITL confirmation metadata, event-flow audit) into the existing lightweight FSM + while loop. The runtime stays a plain Python while loop with explicit state in `agent_runs.status`.
- Risk if ignored: Without ChatError audit, a DeepSeek API failure would leave runs in `executing` indefinitely. Without tool_arguments validation, an LLM returning `tool_arguments: "query=Ontology"` (string instead of dict) would crash execute_tool. Without configurable max_steps, the safety valve is invisible to operators.
- Verification: 38 agent + chat + E2E tests pass. Ruff clean. Commit `ca58506`.
- Interview version: I hardened the Agent loop for real LLM integration without reaching for a framework. Provider failures write audit steps before failing the run. LLM tool arguments are type-checked before execution. max_steps is configurable via environment variable. The loop still runs as a plain Python while loop.

## Deep Agents Is A Pattern Source, Not A Runtime Dependency Yet

- Date: 2026-06-18
- Version: Agent Capability v2 planning
- Type: decision
- Context: LangChain Academy's Deep Agents with LangGraph course raised the question of whether Semantic Lighthouse should adopt a deeper agent harness.
- What happened: Compared Deep Agents / LangGraph ideas against the current product boundary and Agent v2 plan. Updated roadmap, handoff, and Agent Capability v2 design to treat Deep Agents as a reference for todo/planning, context offloading, subagent isolation, HITL, and observe/action audit flow.
- Engineering judgment: The useful ideas are architectural patterns, not necessarily a runtime migration. Todo/planning maps to `plan_json` and `agent_steps`; HITL maps to risky tool confirmation and rejection observations; context offloading maps to auditable summaries, not hidden scratchpads. Semantic Lighthouse's current risk is not lack of agent framework power; it is preserving group-scoped permission checks, deterministic backend rules, auditability, and user-confirmed actions while adding LLM tool choice.
- Risk if ignored: Pulling in LangGraph/Deep Agents too early could turn a focused RAG evidence workspace into a broad autonomous Agent platform, adding framework complexity before the lightweight FSM + `agent_loop()` has proven insufficient.
- Fix or control: Roadmap now has a Phase 7 follow-up for Deep Agents pattern review. Agent Capability v2 explicitly says no LangGraph/Deep Agents runtime unless measured multi-step scenarios outgrow the lightweight loop, such as complex resume, branching, or context offloading that current `agent_runs` + `agent_steps` cannot maintain cleanly.
- Verification: Documentation-only change; verified with `git diff --check`. No runtime behavior changed.
- Interview version: I evaluated Deep Agents as a design reference instead of blindly adding a framework. I kept the project centered on controlled, auditable RAG workflows and created a future adoption gate: use the patterns now, reconsider the runtime only when the lightweight loop has measured limits.

## Agent Tool Loop Without LangGraph — FSM + While Loop + Fake Decisions

- Date: 2026-06-18
- Version: Agent Capability V2.1
- Type: highlight
- Context: Phase 7 had FSM Agent with 3 tools + HITL but no autonomous tool selection. Research surveyed LangGraph/AutoGen, concluded not needed yet.
- What happened: Implemented `agent_loop()` as plain Python while loop — no framework, no graph. `FakeLoopChatClient` with pre-recorded decisions for deterministic testing. `?tool=` param preserves V1 deterministic path alongside V2 loop. `ChatClient.agent_decide()` interface ready for real LLM (V2.2).
- Engineering judgment: Two decisions. (1) No LangGraph — while loop simpler, state transitions explicit in `agent_runs.status`. (2) V1 path alive — `?tool=` keeps 17 eval tests from regressing.
- Verification: 23 agent tests (17 V1 + 6 V2), ruff clean.

## RAG Quality Is Not "Feels Better" — Fixed Queries + Metrics + Gate

- Date: 2026-06-17
- Version: Phase 1.3 (RAG Quality Evaluation v1)
- Type: highlight
- Context: The project had two eval scripts but no baseline, no regression detection, and a question set that tested system internals instead of the product's domain (enterprise AI transformation consulting).
- What happened: Built a three-layer eval harness. (1) 24-question ontology KB eval set across 7 types replacing 16 self-test questions. (2) Added MRR and Precision@5 — now 4 retrieval metrics. (3) `check_eval_thresholds.py`: reads JSON eval output, gates keyword Recall@5 ≥ 0.6 and no-result rate ≤ 0.2, supports baseline regression comparison.
- Engineering judgment: Two separations matter. First, self-test queries and ontology eval queries must live in separate files — mixing them makes results uninterpretable. Second, eval scripts produce data; a separate gate script enforces thresholds. The gate doesn't run eval — it reads eval output. This keeps the runner fast and the gate reusable.
- Risk if ignored: Every retrieval change judged subjectively. Without fixed queries and numeric thresholds, the project cannot prove quality is maintained.
- Verification: 166 pytest; eval scripts produce valid JSON; threshold gate returns exit 0.
- Interview version: I separated RAG quality from feelings — every retrieval change is checked against 24 real consulting questions with annotated expected documents. MRR measures ranking quality; Precision@5 catches noise. A threshold gate fails if recall drops, so quality doesn't silently regress.

## Task Is Not A Todo — Source-Traceable Action Items From RAG Next Steps

- Date: 2026-06-17
- Version: Product Alignment A.3 + v1.1
- Type: highlight
- Context: RAG answers returned `next_steps`, but without confirmation and traceability these suggestions were just text. The system needed to turn AI suggestions into trackable work without becoming a project management tool.
- What happened: Built a lightweight task board where every task records `source_type` + `source_id` — linking back to the exact RAG run that suggested it. Click a task card to inline-expand the source: original question, answer, citations, and knowledge gaps at suggestion time. v1.1 added `status='cancelled'` soft cancel and CSS variable aliases to fix silently-broken task UI styling.
- Engineering judgment: Two decisions enforce the product boundary. (1) No DELETE endpoint — tasks are audit records; cancelled via `status='cancelled'` soft cancel instead, fully reversible (`cancelled → pending`). (2) Source detail fetched lazily from `GET /rag/runs/{id}`, not denormalized — the task stores a pointer, not a copy. This avoids stale data and keeps the task row lightweight.
- Risk if ignored: Tasks become a disconnected CRUD list. Users can't answer "why did I create this?" or "what was the AI's reasoning?" The system degrades from knowledge evidence workspace to generic todo app.
- Fix or control: `source_type` + `source_id` indexed columns. Inline expand via `answerCard({ hideNextSteps: true })`. `sourceCache` Map for instant re-expand. `status='cancelled'` with member-reopen permission.
- Verification: 20 task tests (15 V1 + 5 V1.1), 166 pytest full suite. verify_ui 17/19 (2 known-fragile on fake chat timing).
- Interview version: I designed the task system not as a todo list but as a source-traceability layer. Every task records which RAG answer suggested it. Clicking a task shows the original evidence — so the action stays connected to the AI reasoning. No DELETE because these are audit records; soft cancel keeps the evidence chain intact.

## Chinese Keyword Search Bi-gram Fix — Real Ontology RAG Quality Review

- Date: 2026-06-15
- Version: Phase 3 (P4 quality review)
- Type: highlight
- Context: Real ontology knowledge base (74 docs) imported for 10-question RAG evaluation. Initial keyword search failed to retrieve expected documents.
- What happened: Chinese keyword extraction used regex `[一-鿿]{2,}` which captured entire consecutive Chinese sequences as one ILIKE term (e.g., `%企业为什么需要%`). This required verbatim phrase match — impossible. Additionally, relevance scoring treated all terms equally, so distinctive ASCII terms ("Ontology", "RAG") were drowned by common Chinese bi-grams.
- Fix: (1) `_keyword_terms` splits CJK sequences >=3 chars into overlapping bi-grams. (2) ASCII terms placed first in term list (occupy top-8). (3) `_keyword_search` relevance scoring gives 2x weight to ASCII term matches.
- Verification: "Ontology (本体论)" ranks 3rd for Q1 (was absent). 125 pytest pass. `scripts/run_rag_quality_eval.py` added. Full contract: 20/20 Chinese, 20/20 forbidden-clean, 20/20 citations-traceable, 20/20 confidence-valid, 20/20 audit-complete.
- Interview version: Found a Chinese tokenization blind spot — entire Chinese phrases treated as atomic search terms. Bi-gram splitting + ASCII weighting gave a 10-line fix with measurable ranking improvement, no new dependency.

## Frontend Redesign Round 1 — Product Experience from Console

- Date: 2026-06-13
- Version: Phase 6.6
- Type: highlight
- Context: Frontend was a 6-page developer console with backend labels (RAG, Jobs) and a cold blue/gray palette. No onboarding or primary experience.
- What happened: Warm teal/amber visual system, tabbed auth with brand identity, guided onboarding, `/ask` as primary home with confidence bar and citation cards, user-task navbar labels. Every old page and route preserved. Zero npm, zero backend changes, 12/12 Playwright smoke tests pass.
- Engineering judgment: Additive redesign — CSS tokens upgrade all existing pages automatically. Old routes remain functional for compatibility. Product metaphor (lighthouse = guidance, warmth) now matches the visual language.
- Verification: `python scripts/verify_ui.py` → 12 passed, 0 failed.

## V1 Security Model Is Built Around Failure Modes

- Date: 2026-06-09
- Version: V1.0
- Type: highlight
- Context: The authentication system needed to support future permission-aware RAG retrieval.
- What happened: V1 implements short-lived Access Tokens, httpOnly Refresh Cookies, database-stored refresh token hashes, rotation, replay detection, and group role checks.
- Engineering judgment: Authentication is not just login. For enterprise RAG, identity must feed into authorization and later into retrieval filters.
- Risk if ignored: Future document retrieval could return or cite documents from groups the user should not access.
- Fix or control: Group APIs enforce authentication, membership role checks, and group_id-scoped queries.
- Verification: Tests cover refresh replay, role rejection, and non-member group access rejection.
- Interview version: I designed V1 auth as the security foundation for permission-aware RAG, not as tutorial JWT login.

## V1 Smoke Flow Reached A Running Service

- Date: 2026-06-09
- Version: V1.0
- Type: highlight
- Context: Automated tests had passed, but the service had not yet been exercised as a running API.
- What happened: Started the FastAPI service against a local SQLite database and completed register, login, `/auth/me`, and group creation.
- Engineering judgment: Tests prove logic, but a deliverable service must also start and accept real HTTP requests.
- Risk if ignored: The project could pass tests but still fail as an actual API service.
- Fix or control: Added dev start/stop scripts and performed a smoke flow through HTTP.
- Verification: `/health` returned `ok`; the smoke user created a group and received the `owner` role.
- Interview version: I separated unit/API regression from runtime smoke verification and confirmed the V1 API is usable end to end.

## Refresh Replay Was Verified Over HTTP

- Date: 2026-06-09
- Version: V1.0
- Type: highlight
- Context: Automated tests covered replay detection, but we also needed a running-service verification.
- What happened: Logged in, refreshed once to rotate the Refresh Token, replayed the old token, then tried the newer token again.
- Engineering judgment: The important behavior is not only that old tokens fail, but that replay is treated as session compromise.
- Risk if ignored: A stolen old Refresh Token could reveal compromise without invalidating the active session chain.
- Fix or control: The service returns 401 for old-token replay and revokes the newer token in the same family.
- Verification: HTTP smoke output showed `Refresh token replay detected` for both the old token replay and the newer token after family revoke.
- Interview version: I verified that Refresh Token Rotation handles the failure path, not just the happy path.

## Group Authorization Failure Paths Were Verified

- Date: 2026-06-09
- Version: V1.0
- Type: highlight
- Context: V1 needs to prove group permissions fail safely, not only that Owner actions work.
- What happened: Ran a HTTP smoke flow with Owner, Member, Applicant, and Outsider users.
- Engineering judgment: Permission systems are only credible when forbidden actions are tested.
- Risk if ignored: Member or non-member users could accidentally gain administrative or group-resource access, which would later become RAG document leakage.
- Fix or control: Membership and role checks returned 403 for Member join-request access, Member approval, and Outsider group access; Owner approval succeeded.
- Verification: HTTP smoke statuses: Member list requests 403, Member approve 403, Outsider get group 403, Owner approve 200.
- Interview version: I verified group authorization through negative paths, because future RAG retrieval will inherit this group boundary.

## V1 Passed PostgreSQL-Backed Runtime Verification

- Date: 2026-06-09
- Version: V1.0
- Type: highlight
- Context: SQLite tests and smoke flows were not enough to claim the enterprise persistence path worked.
- What happened: After fixing Docker/WSL/Hypervisor readiness, PostgreSQL started with Docker Compose and Alembic migrated the real Postgres database.
- Engineering judgment: A production-like runtime path must be verified separately from fast local tests.
- Risk if ignored: The project could pass tests while failing on its intended database backend.
- Fix or control: Ran PostgreSQL-backed smoke flows for normal auth/group flow, refresh replay, and group authorization failures.
- Verification: Postgres-backed smoke outputs showed register/login/me/create group succeeded, refresh replay returned 401 and revoked the family, and Member/Outsider authorization failures returned 403.
- Interview version: I verified V1 at three levels: automated tests, SQLite service smoke, and PostgreSQL-backed runtime smoke.

## V1.1 Auth Console Added For Manual Demo

- Date: 2026-06-10
- Version: V1.1
- Type: highlight
- Context: Swagger `/docs` was useful for debugging but not ideal as a project demo surface.
- What happened: Added a minimal `/console` static page for register, login, `/auth/me`, refresh, and logout.
- Engineering judgment: The frontend should demonstrate the V1 auth flow without becoming the main project complexity.
- Risk if ignored: The project would be technically usable but hard to demo outside API tooling.
- Fix or control: Used FastAPI static files and plain HTML/CSS/JS instead of adding a frontend framework.
- Verification: API tests still pass; `/console`, CSS, and JS load; HTTP smoke flow passed through register, login, `/auth/me`, refresh, and logout.
- Interview version: I added a minimal operations console to make the backend capability demonstrable while keeping the V1 focus on authentication and permissions.

## V2 Permission-Aware Document Retrieval

- Date: 2026-06-10
- Version: V2.0
- Type: highlight
- Context: V2 needs to give future RAG a safe document and chunk layer.
- What happened: Added group-scoped documents, group-scoped chunks, Markdown frontmatter parsing, heading-based chunking, local knowledge-base import, single Markdown upload, and keyword search.
- Engineering judgment: Retrieval safety must be proven before answer generation.
- Risk if ignored: RAG could later retrieve or cite documents outside the user's group.
- Fix or control: Every document and chunk carries `group_id`, and all list/detail/search queries filter by `group_id`.
- Verification: Tests cover member read access, Owner/Admin write access, non-member rejection, duplicate import, and cross-group search isolation.
- Interview version: I built retrieval safety before answer generation, because enterprise RAG needs permission-correct citations, not only factually correct text.

## V2.1 Semantic Retrieval Added Behind The Same Group Boundary

- Date: 2026-06-11
- Version: V2.1
- Type: highlight
- Context: V2 keyword search is explainable, but future RAG also needs semantic retrieval.
- What happened: Added an embedding client abstraction, Aliyun provider configuration, fake test provider, chunk embedding fields, rebuild endpoint, and semantic-search endpoint.
- Engineering judgment: Embedding generation should be separated from document ingestion so cloud API failures do not corrupt the document corpus.
- Risk if ignored: Vector retrieval could become a new cross-group leakage path or make imports unreliable.
- Fix or control: Semantic search still filters by `group_id`; tests use deterministic fake embeddings and cover non-member and cross-group failures.
- Verification: `pytest` passed with 26 tests; SQLite migration to `0003` passed; OpenAPI exposes rebuild and semantic-search; PostgreSQL + pgvector smoke passed; real Aliyun `text-embedding-v4` small-sample chain passed.
- Interview version: I added semantic retrieval without moving the permission boundary out of the database.

## V3 Single-Turn RAG Answer API

- Date: 2026-06-11
- Version: V3.0
- Type: highlight
- Context: After V2.1 semantic retrieval, the next useful milestone is a minimal answer-generation loop.
- What happened: Added a group-scoped RAG answer endpoint, DeepSeek-compatible chat provider, fake test provider, structured answer output, citation list, confidence, knowledge gaps, and next steps.
- Engineering judgment: Generation should consume retrieved citations instead of directly reading arbitrary documents or bypassing the permission layer.
- Risk if ignored: The model could produce uncited answers or accidentally use context from the wrong group.
- Fix or control: The answer endpoint checks membership, retrieves chunks with `group_id` filters, and passes only citation snippets into the chat provider.
- Verification: `pytest` passed with 31 tests; tests cover keyword RAG, semantic RAG, non-member rejection, cross-group isolation, and missing DeepSeek key errors.
- Interview version: I connected retrieval to generation while keeping the enterprise security boundary intact.

## V3.1 Local Evidence Gate

- Date: 2026-06-11
- Version: V3.1
- Type: highlight
- Context: A RAG system should not call the model when retrieval returns no evidence.
- What happened: Added a local no-evidence path that returns low confidence, knowledge gaps, next steps, and no citations.
- Engineering judgment: Refusing or deferring is part of answer quality, not a missing feature.
- Risk if ignored: The model could hallucinate a polished answer with no retrieved support.
- Fix or control: The RAG endpoint checks citations before creating a chat client or calling DeepSeek.
- Verification: Tests cover the no-evidence path under `CHAT_PROVIDER=deepseek` without needing `DEEPSEEK_API_KEY`.
- Interview version: I implemented a quality gate so the system can say “knowledge insufficient” instead of pretending.

## V3.2 Cloud Deployment Package

- Date: 2026-06-11
- Version: V3.2
- Type: highlight
- Context: The project needs a real cloud demo path after local V3 RAG passed.
- What happened: Added a production Dockerfile, Docker Compose deployment, production env template, Ubuntu bootstrap script, and deployment guide.
- Engineering judgment: A 2C2G ECS can run the API and pgvector for demo use because model inference stays on cloud APIs.
- Risk if ignored: The project would remain a local-only prototype and be harder to demonstrate in interviews.
- Fix or control: Keep deployment small: one API container, one PostgreSQL/pgvector container, one `.env.production`, one worker, and 2 GiB swap.
- Verification: Production Compose config renders successfully; full test suite still passes with 33 tests; cloud deployment reached healthy API and PostgreSQL containers on Alibaba Cloud ECS.
- Interview version: I containerized the RAG prototype for a small ECS without overbuilding platform infrastructure before the product loop is stable.

## V3.2 Alibaba Cloud ECS Deployment Verified

- Date: 2026-06-11
- Version: V3.2
- Type: highlight
- Context: The local RAG prototype needed a real public demo endpoint.
- What happened: Deployed the API and PostgreSQL/pgvector to an Alibaba Cloud ECS instance with Docker Compose.
- Engineering judgment: For a 2C2G server, model inference stays on external APIs while the server runs only API, database, migration, and health checks.
- Risk if ignored: A local-only project is harder to demonstrate and does not prove basic deployment ability.
- Fix or control: Added 2 GiB swap, used one API worker, ran Alembic migrations on startup, and verified container health.
- Verification: `/docs` is reachable from the public IP; API and PostgreSQL containers are healthy; migrations reached `0003_v21_embeddings`.
- Interview version: I completed a real cloud deployment and verified the runtime stack instead of only showing local tests.

## V3.2 Real Cloud RAG Smoke Passed

- Date: 2026-06-11
- Version: V3.2
- Type: highlight
- Context: After cloud deployment, the project needed proof that the real provider chain worked, not only fake-provider tests.
- What happened: Ran a real cloud smoke chain: register, login, create group, upload Markdown, rebuild embeddings, semantic search, and RAG answer.
- Engineering judgment: Provider integration should be tested with a small controlled sample after local fake-provider regression passes.
- Risk if ignored: The system could pass local tests but fail at the actual cloud API, pgvector, or model-generation boundary.
- Fix or control: Used one small Markdown document and a narrow semantic query to limit cost while validating the full path.
- Verification: DeepSeek returned a grounded answer explaining why Ontology is still useful when an enterprise already has a data platform.
- Interview version: I verified the full production-like RAG chain with real cloud embedding and chat providers on the deployed ECS service.

## V3.3 RAG Run Audit Added

- Date: 2026-06-11
- Version: V3.3
- Type: highlight
- Context: A RAG answer should be replayable and auditable after it is generated.
- What happened: Added `rag_runs`, persisted RAG answers, returned `run_id`, and exposed group-scoped run list/detail APIs.
- Engineering judgment: Historical questions, answers, and citations are enterprise data and must inherit group permissions.
- Risk if ignored: The system could answer questions but provide no way to debug retrieval quality or explain past outputs.
- Fix or control: Store answer, confidence, retrieval method, model, citations, knowledge gaps, next steps, user ID, group ID, and timestamp.
- Verification: `pytest` passed with 35 tests; Alembic migrated from empty SQLite DB to `0004_v33_rag_runs`.
- Interview version: I added auditability to the RAG chain so answers can be reviewed, replayed, and evaluated.

## V2.2 Chunked Multi-Format Upload Added

- Date: 2026-06-11
- Version: V2.2
- Type: highlight
- Context: The document layer needed more than small Markdown upload to support realistic enterprise materials.
- What happened: Added MD/TXT/PDF/DOCX parsing, three-stage chunked upload, instant upload, resumable sessions, idempotent chunk writes, and local disk storage volumes.
- Engineering judgment: Large file handling should be a protocol with integrity checks, not only a larger request size limit.
- Risk if ignored: Upload failures would force full retransmission, duplicate files could pollute retrieval, and parsing failures could create half-ingested documents.
- Fix or control: `init` checks hash and session progress, `chunks` upserts by chunk index, and `complete` verifies chunk completeness plus final SHA-256 before ingestion.
- Verification: `pytest` passed with 40 tests; Alembic migrated from empty SQLite DB to `0005_v22_chunked_uploads`.
- Interview version: I turned document upload into a resumable, auditable ingestion protocol while keeping group-level data isolation.
## V3.4 ETL Pipeline Hardened — Retrospective Review Caught Production Blockers

- Date: 2026-06-12
- Version: V3.4
- Type: highlight
- Context: After the initial V3.4 ETL delivery, a structured code review found six bugs (P1-1 to P2-3), including a NameError that would crash PostgreSQL semantic search and a retry bypass that made the 3-attempt loop dead code for embedding failures.
- What happened: Three CRITICAL bugs were fixed: (1) `PGVECTOR_DIMENSION` undefined in pgvector code paths — hidden by SQLite fallback; (2) `EmbeddingError` caught and short-circuited the retry loop; (3) manual retry on a ready document could destroy existing search results. Three additional quality issues were fixed: step_log mutation not tracked, test assertions too loose to catch failures, and ETL scope not documented.
- Engineering judgment: A review that explicitly hunts for "why would this pass tests but fail in production?" uncovered issues that a green test suite alone would miss. The pgvector NameError is the archetype: SQLite fallback tests are fast but create a blind spot for dialect-specific code paths.
- Risk if ignored: Production deployment would crash on first semantic search request; transient cloud API errors would cause permanent ingestion failures; operators could accidentally take down working search results.
- Fix or control: All P1/P2 bugs fixed with regression tests. Test suite now uses file-backed SQLite to support BackgroundTasks across threads. Ruff lint zero errors. Migration at head.
- Verification: 55 passed, 1 warning; ruff clean; Alembic 0006 at head.
- Interview version: I learned that a green test suite is necessary but not sufficient for deployment confidence. Dialect-specific code paths need a separate smoke gate; every step in a retry loop must propagate errors; and destructive operations on production data need a safety net.

## V2.2 Upload Cleanup And Memory Safety Hardened

- Date: 2026-06-11
- Version: V2.2
- Type: highlight
- Context: V2.2 chunked upload worked functionally but had three engineering gaps: no temp file cleanup, no merged-file cleanup on failure, and full-file memory loading for hash verification.
- What happened: Added streaming hash verification (`verify_file_hash`), temp chunk cleanup (`cleanup_upload_temp_dir`), merged-file cleanup on failure (`cleanup_merged_file`), and tightened upload session GET permission from any Member to Owner/Admin.
- Engineering judgment: Upload correctness includes cleanup, not just ingestion success. Memory safety matters even at 50 MiB limits when the server has only 2 GiB total.
- Risk if ignored: Disk leak in `upload-tmp` and `document-storage`, OOM risk from concurrent upload hash verification, and asymmetric permission surface exposing upload metadata to members.
- Fix or control: Three cleanup paths (success, hash-mismatch, parser-failure) each handle both temp and merged files appropriately. Hash verification streams in 64 KB chunks. Permission aligned across all upload endpoints.
- Verification: 44 tests pass (4 new: cleanup after success, cleanup after hash mismatch, cleanup after parser failure, member GET rejection). Migration smoke clean at `0005_v22_chunked_uploads`.
- Interview version: I hardened the upload chain across three dimensions — disk hygiene, memory safety, and permission consistency — so the protocol is not just functional but resilient under concurrent use on a small server.

## V4.0 Multi-Turn Conversation Memory

- Date: 2026-06-12
- Version: V4.0
- Type: highlight
- Context: After V3 RAG single-turn was stable, the next engineering step was multi-turn conversation memory — not a fully autonomous agent, but a controlled mechanism for maintaining context across turns.
- What happened: Added `conversations` + `conversation_messages` tables with `group_id`/`user_id` isolation; 4 API endpoints (create, list, get detail, send message); multi-turn history injection into LLM prompts via `history` parameter on `ChatClient.answer_question`; full audit trail via message persistence.
- Engineering judgment: Multi-turn should extend the existing RAG pipeline (retrieve → cite → generate → audit) rather than replace it. Conversation memory inherits the same `group_id` boundary and user-level isolation that every other data path enforces. History injection is a prompt-layer concern, not a new storage or state management layer.
- Risk if ignored: Building a full agent framework before conversation basics would couple tool-calling, memory governance, and workflow planning into a single delivery, making each layer harder to test and explain independently.
- Fix or control: History limited to 10 rounds (20 messages); user-scoped ownership enforced on all GET/POST paths; `ChatClient.answer_question` accepts optional `history` parameter with backward-compatible default; no-change to existing RAG single-turn API.
- Verification: 91 passed (77 existing + 14 new), 0 failures; ruff clean; Alembic migrated from empty SQLite DB to `0007_v4_conversations` (head).
- Interview version: I added multi-turn conversation memory as a thin extension of the RAG audit chain — same permission boundary, same retrieval pipeline, same citation generation — so the system can sustain a consulting dialogue without a heavyweight agent framework.

## V4.1 Controlled Tool Calling

- Date: 2026-06-12
- Version: V4.1
- Type: highlight
- Context: After V4.0 conversation memory was stable, the next step was letting the Agent request predefined tools — without building a full autonomous agent framework.
- What happened: Added a server-side tool registry (`AVAILABLE_TOOLS`) with one tool (`search_knowledge_base`). Extended `ChatClient` with `generate_response()` that returns either a direct `ChatAnswer` or a `ToolCall`. Implemented a single-level tool loop in `send_message`: LLM requests tool → server executes with `group_id` boundary → tool result injected into conversation history → LLM produces final answer. Tool execution and results are persisted as `ConversationMessage` records with `role="tool"` and `tool_calls` JSON for audit.
- Engineering judgment: Tool calling should be a deterministic server-side execution, not a model-controlled sandbox. The tool registry is a hardcoded whitelist; unknown tools return errors. The loop depth is bounded at 1 (no recursion). All tool searches inherit the caller's `group_id` permission — the model can't escape its data boundary.
- Risk if ignored: Without tool calling, the Agent is limited to the initial retrieval, which may miss relevant results. But with unrestricted tool access, the model could attempt dangerous actions or access cross-group data.
- Fix or control: Whitelist-only tool registry; `_execute_tool` validates tool name before execution; tool results capped at 2000 characters; `_messages_with_tools` instructs the model to request at most one tool; final answer path degrades gracefully if no answer produced.
- Verification: 96 passed (91 existing + 5 new tool tests), 0 failures; ruff clean; all existing conversation tests pass without modification.
- Interview version: I added controlled tool calling as a server-side gate rather than a model-side capability — the Agent can ask for help, but the server decides what's safe to execute.

## Phase 6 Frontend Engineering Console

- Date: 2026-06-12
- Version: V6.0
- Type: highlight
- Context: After backend phases 0-4.1 stabilized, the project needed a real, maintainable frontend for demo and operations — not a throwaway Swagger-only experience.
- What happened: Built a complete SPA console using vanilla JS ES modules with a hash-based client router. Six pages cover the full demo flow: Auth (login/register), Groups (list/create/join), Documents (upload/search/archive), Ingestion Jobs (list/detail/retry), RAG (question → answer → citations → confidence → knowledge gaps), and Conversations (list + multi-turn chat with tool call display). Zero npm dependencies, zero build step — served directly by FastAPI's existing StaticFiles mount.
- Engineering judgment: A frontend for a backend-heavy prototype should be as lightweight as the backend's own toolchain. Adding a React/Vue build pipeline for 6 CRUD pages would burden future maintainers with node_modules, webpack configs, and version drift. ES modules are native, `/console` loads instantly, and the module-per-page structure is trivially extensible.
- Risk if ignored: Without a real UI, every demo requires Swagger + curl — unusable for non-engineers and unconvincing in interviews. But building a "big admin panel" would add maintenance debt disproportionate to the project's stage.
- Fix or control: Vanilla JS ES modules, hash-based routing (~50 lines), shared CSS custom properties, one file per page/component. Permission-aware: Owner/Admin see archive/retry buttons; Members don't. Auth state drives navbar visibility. No backend changes required.
- Verification: 96 backend tests pass (zero regression); ruff clean; all 11 frontend files load via ES module imports; `/console` serves the new SPA.
- Interview version: I built a real frontend console without installing a single npm package — the same `uvicorn` command that serves the API also serves the SPA, and the module-per-page structure keeps the codebase explainable.

## Phase 7 Agent Orchestration — Lightweight State Machine

- Date: 2026-06-12
- Version: V7.0
- Type: highlight
- Context: After V4.1 single-tool Agent was stable, the next step was multi-step Agent workflows with explicit state, audit trail, human-in-the-loop, and long-term memory — without introducing LangGraph or AutoGen.
- What happened: Built a lightweight FSM (plan→execute→observe→conclude) on SQLAlchemy. Added 3 tables, 8 API endpoints, and a 3-tool registry with role requirements and risk flags. Every step records: thought, action_type, action_detail, observation, status, and error_message. Human-in-the-loop: risky tools pause the run; user confirms/rejects via API.
- Engineering judgment: The workflow is linear — not a DAG, not multi-agent. A 50-line state machine with persisted transitions is more explainable than LangGraph's StateGraph with checkpointers. Framework cost (dependency, mental model, serialization contract) is not justified by problem complexity.
- Risk if ignored: Without step-level auditing, multi-tool Agent runs are black boxes — impossible to debug why a search failed or what the Agent was "thinking" at each step.
- Fix or control: Every step has immutable `thought`. Failed steps have `error_message`. Risky tools flagged `is_risky=True`. Human confirmation recorded as `action_type=ask_user`. Memory scoped user/group with TTL.
- Verification: 10 agent tests pass; ruff clean; Alembic at `0008_v7_agent_orchestration`.
- Interview version: I built a multi-step Agent orchestrator as a deterministic state machine — when something goes wrong, you read every step the Agent took, not guess.

## Claude Code Handoff Memory Established

- Date: 2026-06-11
- Version: Handoff
- Context: The project may move from Codex-led development to Claude Code-led development.
- What happened: Added `CLAUDE.md`, `docs/agent-handoff.md`, and `docs/engineering-memory/learning-index.md` so a new coding agent can recover project intent, current state, verification results, risks, and next steps without relying on chat history.
- Engineering judgment: Agent memory should live in repo-owned documentation, not in transient conversations. The handoff path must be short enough to read but specific enough to constrain future work.
- Risk if ignored: A new agent could duplicate work, skip tests, introduce unexplained architecture, or miss the current V2.2 upload-chain risks.
- Fix or control: `CLAUDE.md` defines the read order and working rules; `agent-handoff.md` stores current state and next priority; `learning-index.md` summarizes practiced concepts and weak points.
- Verification: `pytest` passed with 40 tests; Alembic migrated from empty SQLite DB to `0005_v22_chunked_uploads`.
- Interview version: I treated AI-assisted development handoff as an engineering artifact, so project memory, risk state, and verification results are reproducible across tools and sessions.

## RAG Citation Quantity And Diversity Control

- Date: 2026-06-16
- Version: RAG Quality
- Type: highlight
- Context: The UI could only use the backend default citation count, and citation assembly followed raw retrieval order. When one document produced many adjacent chunks, citations could look numerous but still lack source diversity.
- What happened: Exposed 5/8/10 citation choices in the knowledge问答 and RAG调试台 pages. Added backend citation candidate filtering for empty or zero-score chunks. Added a first-pass per-document cap so the answer context prefers multiple source documents before overflowing repeated chunks from the same document.
- Engineering judgment: More citations are not automatically better. A consulting answer needs enough evidence, but it also needs diversified sources and clear boundaries on context size. The backend still enforces the schema limit and `rag_max_context_chars`, so the UI cannot create unlimited LLM context.
- Risk if ignored: The answer could appear well-cited while actually relying on repeated neighboring chunks from a single document, weakening confidence and making audits misleading.
- Fix or control: `RagAnswerRequest.limit` drives retrieval size; `_prioritize_citation_candidates` improves source diversity; `_usable_citation_candidate` filters zero-score and empty chunks. Regression tests cover expanded citation count, document diversity ordering, and bad-candidate filtering.
- Verification: `tests/test_rag.py tests/test_retrieval.py` passed 48 tests; full pytest passed 146 tests; UI smoke passed 13/13.
- Interview version: I separated citation quantity from citation quality. Users can request more sources, but the system still filters weak candidates and prevents one document from monopolizing the context.

## Tencent Cloud Deployment Verified

- Date: 2026-06-16
- Version: Cloud Deployment
- Type: highlight
- Context: The project needed a current cloud demo deployment after local RAG, frontend console, and Agent orchestration had stabilized.
- What happened: Deployed the project on Tencent Cloud Lighthouse using the Ubuntu Server 24.04 Docker CE image. The clean deploy archive was uploaded through the console, extracted to `/opt/semantic-lighthouse`, and started with production Docker Compose.
- Engineering judgment: Starting from a Docker CE image reduced bootstrap risk, but the real confidence came from smoke testing the application chain, not just seeing containers start.
- Risk if ignored: A deployment could look successful while auth, upload, retrieval, migrations, or citation output are broken.
- Fix or control: Verified both production containers were healthy, Alembic reached `0009_v9_rag_audit`, `/health` returned 200, and `scripts/deploy/smoke-cloud.sh` completed the auth -> upload -> keyword RAG path with one citation.
- Verification: `semantic-lighthouse-api` and `semantic-lighthouse-postgres` healthy; quick smoke reported `rag ok`, `confidence: medium`, `retrieval_method: keyword`, and `citation_count: 1`.
- Interview version: I deployed the RAG/Agent prototype to a small cloud server and proved the end-to-end demo path with a smoke test, not just a container health check.

## Product Boundary Re-centered On Actionable RAG

- Date: 2026-06-17
- Version: Product Alignment
- Type: highlight
- Superseded by: Product Alignment v2 (2026-06-18), which keeps this RAG-to-action loop as the foundation but updates the north star to Ontology semantic operating layer.
- Context: The project had grown from auth/RAG into conversations, Agent orchestration, web-search design, and frontend workflows. Without a sharper product boundary, future iterations could drift into "everything is Agent" or a vague consulting chatbot.
- What happened: Added `docs/product-alignment-prd.md` and synchronized the entry files around a single positioning: Semantic Lighthouse is a permission-aware knowledge evidence workspace for enterprise AI transformation. The near-term loop is answer evidence -> confidence/gaps -> next steps -> user-confirmed lightweight task.
- Engineering judgment: I separated three levels of AI behavior: answering, suggesting, and executing. Answering can be handled by trusted RAG; suggesting can produce next steps; executing or mutating state needs explicit permission, group isolation, audit, and user confirmation.
- Risk if ignored: The project could over-design Agent capabilities before the RAG and evidence workflow is product-clear, making the system harder to explain and easier to misuse.
- Fix or control: Agent is documented as a controlled coordination layer only for multi-step, tool-based, auditable workflows. Web search remains Discovery until low-confidence question validation proves value. Task creation is user-confirmed, not automatic.
- Verification: Documentation-only change; verified with `git diff --check` and entry-file search for stale product positioning.
- Interview version: I did not keep adding Agent features just because they were possible. I re-centered the product on a trusted RAG-to-action loop and defined where AI may answer, where it may suggest, and where the user must approve.
