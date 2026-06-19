# Manufacturing Pilot Demo v1 — Report

Generated: 2026-06-19T08:41:28Z
Group: Manufacturing Pilot Demo v1 (95017692-2aa9-4b07-a5e1-b3c0f1bc5e82)

## Pipeline

1. Created 11 business_v1 drafts (2 OT + 6 Property + 2 Link + 1 Action)
2. Batch reviewed → 11 accepted (reviewer: f8629e70-eb9f-4e0e-a689-8311a96a37fb, at: 2026-06-19T08:41:29.282409Z)
3. Built immutable package (id: deb5b4b0-7cbd-4392-b8de-ed1824568e9e)
4. Exported compiled contract via API
5. Verified idempotent rebuild
6. Verified cross-group isolation

## Results

- **Package quality**: PASS
- **Compiled counts**: 2 object_types / 6 properties / 2 link_types / 1 action_type
- **semantic_hash**: sha256:53254cd806f80e2aa64840f6cab66aadbc771cf913c3819c1cf3be6c78a11769
- **Iterative stability**: semantic_hash identical across rebuilds
- **Audit**: all 11 drafts have reviewed_by/reviewed_at; package has created_by
- **Provenance**: source_package_id=deb5b4b0-7cbd-4392-b8de-ed1824568e9e version=1
- **Cross-group isolation**: 403 confirmed
- **Action declaration-only**: no handler/endpoint/SQL/tool binding in declared_effects

## Boundary

- No object instances stored. No ERP/MES/PLC connected.
- CreateWorkOrder declared, never executed.
- No SDK, MCP, Graph RAG, or Agent tooling.
- Independent demo group — does not share data with Phase 12 knowledge_meta group.
- F:\ontology-kb\knowledge-graph unchanged.
