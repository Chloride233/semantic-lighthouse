# Ontology Governance Demo Report

**Date**: 2026-06-18
**KB**: F:\ontology-kb\knowledge-graph
**DB**: temporary SQLite (`sqlite+pysqlite:///F:/semantic-lighthouse/.tmp/phase9-real-kb-demo.db`)

## Import & Scan

| Metric | Count |
|--------|-------|
| Imported | 74 |
| Skipped | 5 |
| Scanned (ready) | 74 |
| Entities | 74 |
| Relations | 186 |
| Issues | 97 |

## Entities by Type

| entityType | Count |
|------------|-------|
| Concept | 44 |
| Case | 12 |
| Vendor | 8 |
| Product | 4 |
| Methodology | 3 |
| FAQ | 1 |
| Person | 1 |
| Proposal | 1 |

## Relations by Status

| Status | Count |
|--------|-------|
| resolved | 96 |
| unresolved | 90 |

## Issues by Code

| Code | Count | Severity |
|------|-------|----------|
| unresolved_wikilink | 90 | warning |
| stale_eval_gold_doc_id | 7 | warning |

### Unresolved Wikilinks (sample)

- `research/vendor-comparison-matrix.md` ← `案例: 银行 — 客户 360 统一视图`
- `research/vendor-comparison-matrix.md` ← `案例: 市级政府 — 跨部门数据共享与协同`
- `healthcare-patient-view-palantir.md` ← `案例: 医疗机构 — 患者旅程全流程管理`
- `research/palantir-architecture.md` ← `案例: 医疗机构 — 患者旅程全流程管理`
- `writeback-dataset.md` ← `Action Type`

### Stale Eval Gold Doc IDs

- `cases/banking-knowledge-graph-customer-360` → questions: C2
- `cases/healthcare-ontology-patient-modeling` → questions: C3
- `concepts/agent` → questions: F1
- `concepts/ontology-sdk` → questions: A4
- `concepts/rag` → questions: D3

## Boundaries

- ✅ External KB not modified
- ✅ No Graph RAG / graph DB
- ✅ No modeling studio / editor
- ✅ Agent cannot auto-write ontology
- ✅ All read models are group-scoped, permission-aware

## Next Steps

- Phase 10 planning
- Polish demo scripts for portfolio
- Consider KB content curation from governance findings