# Ontology Curation Demo Report

**Date**: 2026-06-18
**KB**: F:\ontology-kb\knowledge-graph
**DB**: temporary SQLite (`sqlite+pysqlite:///F:/semantic-lighthouse/.tmp/phase10-curation-demo.db`)

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

| Code | Count |
|------|-------|
| unresolved_wikilink | 90 |
| stale_eval_gold_doc_id | 7 |

## Triage Summary

Triage is **deterministic rule-based**, not LLM-driven.
All recognized issue codes are marked `confirmed` (no automated ignoring).

| State | Count |
|-------|-------|
| confirmed | 97 |
| pending | 0 |

### Triage Rules Applied

- `unresolved_wikilink` → classified by `target_path`:
  - `research/*` → `missing_research_doc_or_directory`
  - `concepts/*`, `vendors/*`, `products/*`, `methodologies/*`, `cases/*`, `persons/*`, `proposals/*`, `faqs/*` → `missing_or_renamed_entity_doc`
  - other → `review_link_target`
- `stale_eval_gold_doc_id` → `update_eval_gold_or_add_missing_doc`
- `duplicate_title` / `duplicate_alias` → `resolve_identity_conflict`
- Other codes → left `pending`

### Scan Persistence Check

Re-scan after triage: triage persisted = **YES**
(confirmed before = 97, confirmed after = 97)

## Curation Backlog

**39 backlog entries** generated from 97 confirmed issues.

### Action Type Distribution

| Action Type | Count |
|-------------|-------|
| review_link_target | 30 |
| update_eval_gold_doc_id | 7 |
| create_missing_research_doc | 2 |

### Priority Distribution

| Priority | Count |
|----------|-------|
| high | 20 |
| medium | 19 |

### Top Backlog Items

#### 1. [HIGH] review_link_target

- **Target**: `ontology.md`
- **Issue code**: `unresolved_wikilink`
- **Affected**: 11 document(s)
- **Examples**: `concepts/action-type.md`, `concepts/aip.md`, `concepts/data-integration.md`, `concepts/functions.md`, `concepts/graph-rag.md`
- **Suggested action**: Review wikilink target `ontology.md`. 11 referencing documents wikilink to this path but it does not resolve. Determine whether a new document is needed, the link should be updated to point to an existing entity, or the link should be removed.

#### 2. [HIGH] review_link_target

- **Target**: `object-type.md`
- **Issue code**: `unresolved_wikilink`
- **Affected**: 8 document(s)
- **Examples**: `concepts/action-type.md`, `concepts/functions.md`, `concepts/link-type.md`, `concepts/mcp.md`, `concepts/object-view.md`
- **Suggested action**: Review wikilink target `object-type.md`. 8 referencing documents wikilink to this path but it does not resolve. Determine whether a new document is needed, the link should be updated to point to an existing entity, or the link should be removed.

#### 3. [HIGH] review_link_target

- **Target**: `workshop.md`
- **Issue code**: `unresolved_wikilink`
- **Affected**: 7 document(s)
- **Examples**: `concepts/action-type.md`, `concepts/aip.md`, `concepts/functions.md`, `concepts/object-type.md`, `concepts/object-view.md`
- **Suggested action**: Review wikilink target `workshop.md`. 7 referencing documents wikilink to this path but it does not resolve. Determine whether a new document is needed, the link should be updated to point to an existing entity, or the link should be removed.

#### 4. [HIGH] review_link_target

- **Target**: `action-type.md`
- **Issue code**: `unresolved_wikilink`
- **Affected**: 6 document(s)
- **Examples**: `concepts/aip.md`, `concepts/functions.md`, `concepts/mcp.md`, `concepts/object-type.md`, `concepts/ontology.md`
- **Suggested action**: Review wikilink target `action-type.md`. 6 referencing documents wikilink to this path but it does not resolve. Determine whether a new document is needed, the link should be updated to point to an existing entity, or the link should be removed.

#### 5. [HIGH] review_link_target

- **Target**: `link-type.md`
- **Issue code**: `unresolved_wikilink`
- **Affected**: 5 document(s)
- **Examples**: `concepts/action-type.md`, `concepts/object-type.md`, `concepts/object-view.md`, `concepts/ontology.md`, `concepts/property.md`
- **Suggested action**: Review wikilink target `link-type.md`. 5 referencing documents wikilink to this path but it does not resolve. Determine whether a new document is needed, the link should be updated to point to an existing entity, or the link should be removed.

#### 6. [HIGH] create_missing_research_doc

- **Target**: `research/vendor-comparison-matrix.md`
- **Issue code**: `unresolved_wikilink`
- **Affected**: 4 document(s)
- **Examples**: `cases/finance-customer-360-baidu.md`, `cases/government-cross-agency-data-sharing.md`, `faqs/client-faq.md`, `proposals/manufacturing-mid-size-ontology-pilot.md`
- **Suggested action**: Create the missing research document `research/vendor-comparison-matrix.md`. 4 referencing documents link to this path. If the research directory was intentionally excluded from KB, update wikilinks to point to existing concept documents instead.

#### 7. [HIGH] review_link_target

- **Target**: `property.md`
- **Issue code**: `unresolved_wikilink`
- **Affected**: 4 document(s)
- **Examples**: `concepts/action-type.md`, `concepts/link-type.md`, `concepts/object-type.md`, `concepts/object-view.md`
- **Suggested action**: Review wikilink target `property.md`. 4 referencing documents wikilink to this path but it does not resolve. Determine whether a new document is needed, the link should be updated to point to an existing entity, or the link should be removed.

#### 8. [HIGH] review_link_target

- **Target**: `inbox/信息化的基础认识.pdf.md`
- **Issue code**: `unresolved_wikilink`
- **Affected**: 4 document(s)
- **Examples**: `concepts/approval-workflow.md`, `concepts/cross-system-integration.md`, `concepts/enterprise-it-product-types.md`, `concepts/master-data-management.md`
- **Suggested action**: Review wikilink target `inbox/信息化的基础认识.pdf.md`. 4 referencing documents wikilink to this path but it does not resolve. Determine whether a new document is needed, the link should be updated to point to an existing entity, or the link should be removed.

#### 9. [HIGH] review_link_target

- **Target**: `functions.md`
- **Issue code**: `unresolved_wikilink`
- **Affected**: 3 document(s)
- **Examples**: `concepts/action-type.md`, `concepts/ontology.md`, `concepts/osdk.md`
- **Suggested action**: Review wikilink target `functions.md`. 3 referencing documents wikilink to this path but it does not resolve. Determine whether a new document is needed, the link should be updated to point to an existing entity, or the link should be removed.

#### 10. [HIGH] review_link_target

- **Target**: `b2b-product-bilateral-game.md`
- **Issue code**: `unresolved_wikilink`
- **Affected**: 3 document(s)
- **Examples**: `concepts/ai-office-ethics.md`, `concepts/algorithm-power-bias.md`, `concepts/product-positioning-four-questions.md`
- **Suggested action**: Review wikilink target `b2b-product-bilateral-game.md`. 3 referencing documents wikilink to this path but it does not resolve. Determine whether a new document is needed, the link should be updated to point to an existing entity, or the link should be removed.

#### 11. [HIGH] review_link_target

- **Target**: `mcp.md`
- **Issue code**: `unresolved_wikilink`
- **Affected**: 3 document(s)
- **Examples**: `concepts/aip.md`, `concepts/ontology.md`, `concepts/osdk.md`
- **Suggested action**: Review wikilink target `mcp.md`. 3 referencing documents wikilink to this path but it does not resolve. Determine whether a new document is needed, the link should be updated to point to an existing entity, or the link should be removed.

#### 12. [HIGH] review_link_target

- **Target**: `osdk.md`
- **Issue code**: `unresolved_wikilink`
- **Affected**: 3 document(s)
- **Examples**: `concepts/functions.md`, `concepts/mcp.md`, `concepts/ontology.md`
- **Suggested action**: Review wikilink target `osdk.md`. 3 referencing documents wikilink to this path but it does not resolve. Determine whether a new document is needed, the link should be updated to point to an existing entity, or the link should be removed.

#### 13. [HIGH] review_link_target

- **Target**: `aip.md`
- **Issue code**: `unresolved_wikilink`
- **Affected**: 3 document(s)
- **Examples**: `concepts/graph-rag.md`, `concepts/mcp.md`, `concepts/ontology.md`
- **Suggested action**: Review wikilink target `aip.md`. 3 referencing documents wikilink to this path but it does not resolve. Determine whether a new document is needed, the link should be updated to point to an existing entity, or the link should be removed.

#### 14. [HIGH] update_eval_gold_doc_id

- **Target**: `cases/banking-knowledge-graph-customer-360`
- **Issue code**: `stale_eval_gold_doc_id`
- **Affected**: 1 document(s)
- **Examples**: `F:\semantic-lighthouse\docs\eval\rag-queries-ontology.json`
- **Suggested action**: Update eval gold document ID `cases/banking-knowledge-graph-customer-360` in `docs/eval/rag-queries-ontology.json`. Either the document does not exist in the current KB, or the expected_doc_id is stale. Review the referenced questions and correct the doc ID to match an available KB document.

#### 15. [HIGH] update_eval_gold_doc_id

- **Target**: `cases/healthcare-ontology-patient-modeling`
- **Issue code**: `stale_eval_gold_doc_id`
- **Affected**: 1 document(s)
- **Examples**: `F:\semantic-lighthouse\docs\eval\rag-queries-ontology.json`
- **Suggested action**: Update eval gold document ID `cases/healthcare-ontology-patient-modeling` in `docs/eval/rag-queries-ontology.json`. Either the document does not exist in the current KB, or the expected_doc_id is stale. Review the referenced questions and correct the doc ID to match an available KB document.

#### 16. [HIGH] update_eval_gold_doc_id

- **Target**: `concepts/agent`
- **Issue code**: `stale_eval_gold_doc_id`
- **Affected**: 1 document(s)
- **Examples**: `F:\semantic-lighthouse\docs\eval\rag-queries-ontology.json`
- **Suggested action**: Update eval gold document ID `concepts/agent` in `docs/eval/rag-queries-ontology.json`. Either the document does not exist in the current KB, or the expected_doc_id is stale. Review the referenced questions and correct the doc ID to match an available KB document.

#### 17. [HIGH] update_eval_gold_doc_id

- **Target**: `concepts/ontology-sdk`
- **Issue code**: `stale_eval_gold_doc_id`
- **Affected**: 1 document(s)
- **Examples**: `F:\semantic-lighthouse\docs\eval\rag-queries-ontology.json`
- **Suggested action**: Update eval gold document ID `concepts/ontology-sdk` in `docs/eval/rag-queries-ontology.json`. Either the document does not exist in the current KB, or the expected_doc_id is stale. Review the referenced questions and correct the doc ID to match an available KB document.

#### 18. [HIGH] update_eval_gold_doc_id

- **Target**: `concepts/rag`
- **Issue code**: `stale_eval_gold_doc_id`
- **Affected**: 1 document(s)
- **Examples**: `F:\semantic-lighthouse\docs\eval\rag-queries-ontology.json`
- **Suggested action**: Update eval gold document ID `concepts/rag` in `docs/eval/rag-queries-ontology.json`. Either the document does not exist in the current KB, or the expected_doc_id is stale. Review the referenced questions and correct the doc ID to match an available KB document.

#### 19. [HIGH] update_eval_gold_doc_id

- **Target**: `vendors/huawei-fusioninsight`
- **Issue code**: `stale_eval_gold_doc_id`
- **Affected**: 1 document(s)
- **Examples**: `F:\semantic-lighthouse\docs\eval\rag-queries-ontology.json`
- **Suggested action**: Update eval gold document ID `vendors/huawei-fusioninsight` in `docs/eval/rag-queries-ontology.json`. Either the document does not exist in the current KB, or the expected_doc_id is stale. Review the referenced questions and correct the doc ID to match an available KB document.

#### 20. [HIGH] update_eval_gold_doc_id

- **Target**: `vendors/palantir-foundry`
- **Issue code**: `stale_eval_gold_doc_id`
- **Affected**: 1 document(s)
- **Examples**: `F:\semantic-lighthouse\docs\eval\rag-queries-ontology.json`
- **Suggested action**: Update eval gold document ID `vendors/palantir-foundry` in `docs/eval/rag-queries-ontology.json`. Either the document does not exist in the current KB, or the expected_doc_id is stale. Review the referenced questions and correct the doc ID to match an available KB document.

*(19 more entries not shown)*

## Boundaries

- ✅ External KB not modified
- ✅ No Graph RAG / graph DB
- ✅ No modeling studio / editor
- ✅ Agent cannot auto-write ontology
- ✅ Curation backlog is human action guidance only — no automated KB fix
- ✅ Triage is deterministic (rule-based), not LLM-driven
- ✅ All read models are group-scoped, permission-aware

## Next Steps

- Phase 10.3: Ontology graph UX polish (filterable graph, improved labels, edge hover, mobile)
- Optional: portfolio demo script polish
- Human curator reviews and acts on backlog items at their discretion