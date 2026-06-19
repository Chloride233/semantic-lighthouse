# Manufacturing Pilot Demo v1 — Report

Generated: 2026-06-19T08:51:45Z
Group: Manufacturing Pilot Demo v1 (f71d2df2-f981-4ec9-8ff8-37c20425156f)

## Pipeline

1. Created 11 business_v1 drafts (2 OT + 6 Property + 2 Link + 1 Action)
2. Batch reviewed → 11 accepted (reviewer: cf22985b-9a17-4719-abba-26fd122550fe, at: 2026-06-19T08:51:46.229662Z)
3. Built immutable package (id: 8dd56633-f4f1-4a51-b2ef-16f6ce6f99b5)
4. Exported compiled contract via API
5. Verified idempotent rebuild
6. Verified cross-group isolation

## Results

- **Package quality**: PASS
- **Compiled counts**: 2 object_types / 6 properties / 2 link_types / 1 action_type
- **semantic_hash**: sha256:53254cd806f80e2aa64840f6cab66aadbc771cf913c3819c1cf3be6c78a11769
- **Iterative stability**: semantic_hash identical across rebuilds
- **Audit**: all 11 drafts have reviewed_by/reviewed_at; package has created_by
- **Provenance**: source_package_id=8dd56633-f4f1-4a51-b2ef-16f6ce6f99b5 version=1
- **Cross-group isolation**: 403 confirmed
- **Action declaration-only**: no handler/endpoint/SQL/tool binding in declared_effects

## Boundary

- No object instances stored. No ERP/MES/PLC connected.
- CreateWorkOrder declared, never executed.
- No SDK, MCP, Graph RAG, or Agent tooling.
- Independent demo group — does not share data with Phase 12 knowledge_meta group.
- F:\ontology-kb\knowledge-graph unchanged.
