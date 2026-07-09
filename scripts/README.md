# Scripts Index

This directory contains active smoke checks, ontology pipeline utilities, deployment helpers, and historical demo scripts. Keep scripts when they verify a named project capability or preserve a still-useful delivery slice.

## Active Smoke And Verification

| Script | Purpose |
|--------|---------|
| `run_semantic_ci.py` | Offline Semantic CI gate for data-pack contract, mapping, rules, governance feedback, and artifact hashes |
| `build_governance_review_packet.py` | Build offline reviewer-facing packets from Semantic CI governance candidates |
| `build_adventureworks_ontology_seed.py` | Build offline AdventureWorks ontology seed JSON/Markdown from Semantic CI artifacts |
| `build_governance_review_workspace.py` | Build offline pending-decision workspace for governance candidate review |
| `build_governance_decision_template.py` | Build human-fillable offline governance decision template from pending review items |
| `apply_governance_review_decisions.py` | Apply offline governance review decisions into accepted-change artifacts |
| `build_accepted_ontology_drafts.py` | Build offline accepted ontology drafts from accepted governance changes |
| `build_offline_model_package.py` | Build offline model package bridge artifact from accepted ontology drafts |
| `build_offline_dataset_binding.py` | Build offline dataset binding bridge artifact from a built model package and data-pack metadata |
| `build_offline_runtime_query_plan.py` | Build offline explain-only runtime query dry-run plans from dataset bindings |
| `build_semantic_asset_feedback.py` | Build offline semantic asset feedback backlog from review, package, binding, and runtime readiness state |
| `build_offline_acceptance_report.py` | Build offline end-to-end semantic loop acceptance report from all chain artifacts |
| `export_adventureworks.py` | Export a focused AdventureWorks raw CSV + manifest benchmark pack through SSH/sqlcmd |
| `map_adventureworks_to_semantic_pack.py` | Map the raw AdventureWorks export into the 13-table Semantic CI manufacturing contract |
| `smoke_fde_demo.py` | End-to-end Phase 19 FDE-style smoke chain using fake providers and temporary SQLite |
| `smoke_http_api.py` | HTTP API smoke coverage |
| `verify_ui.py` | Frontend console smoke check |
| `check_doc_alignment.py` | Documentation/status alignment check |
| `run_eval.py`, `run_rag_quality_eval.py`, `eval/evaluate.py` | Retrieval/RAG evaluation helpers |
| `check_eval_thresholds.py` | Eval threshold guard |

## Phase 19 Ontology Operationalization

| Script | Purpose |
|--------|---------|
| `generate_manufacturing_dataset.py` | Generate synthetic manufacturing data packs |
| `validate_manufacturing_data_pack.py` | Validate manifest, files, counts, and data-pack contract |
| `generate_mapping_contract.py` | Generate field-to-business-property mapping contracts |
| `validate_mapping_contract.py` | Validate mapping contract structure and references |
| `validate_business_rules.py` | Run deterministic business rule checks |
| `generate_governance_feedback.py` | Produce human-reviewable governance candidates |

## Historical Ontology Demos

These scripts are retained as historical delivery slices and regression references. Do not expand them by default.

| Script | Slice |
|--------|-------|
| `run_ontology_curation_demo.py` | Ontology curation workflow |
| `run_ontology_governance_demo.py` | Governance workflow |
| `run_ontology_model_package_demo.py` | Model package workflow |
| `run_ontology_modeling_demo.py` | Modeling draft workflow |
| `run_manufacturing_pilot_demo.py` | Manufacturing pilot narrative |

## Development And Deployment Helpers

| Path | Purpose |
|------|---------|
| `start_local_app.ps1`, `start_local_app.bat`, `start_local_preview.ps1` | Local app startup helpers |
| `dev/` | Local development helper scripts |
| `deploy/` | Reference cloud bootstrap and smoke scripts |
| `docker/` | Container startup helper |
| `screenshots_f2b.py`, `screenshots_legacy_polish.py` | UI screenshot helpers |
| `scan_encoding.py` | Encoding scan helper |

## Research-Only

| Script | Boundary |
|--------|----------|
| `download_ecommerce_datasets.py` | External dataset acquisition helper; not part of the core smoke path |

## Slimming Rule

Before deleting a script, check whether it is referenced by tests, docs, README files, or the current project status. Runtime, migration, permission, and audit coverage are not cleanup targets.
