# Ontology Curation Demo Report

**Date**: 2026-06-18
**KB**: F:\ontology-kb\knowledge-graph
**DB**: temporary SQLite

## Import & Scan

| Metric | Count |
|--------|-------|
| Imported | 74 |
| Entities | 74 |
| Relations | 186 |
| Issues | 97 |

## Triage

| Status | Count |
|--------|-------|
| confirmed | 97 |

### Issues by Code

| Code | Count |
|------|-------|
| unresolved_wikilink | 90 |
| stale_eval_gold_doc_id | 7 |

## Curation Backlog

### Top 15 Items

### 1. [HIGH] review_link_target
- **Target**: `ontology.md` — 11 issues
- Example: Wikilink target is unresolved: ontology.md
- Action: Verify whether 'ontology.md' should exist.

### 2. [HIGH] review_link_target
- **Target**: `object-type.md` — 8 issues
- Example: Wikilink target is unresolved: object-type.md
- Action: Verify whether 'object-type.md' should exist.

### 3. [HIGH] review_link_target
- **Target**: `workshop.md` — 7 issues
- Example: Wikilink target is unresolved: workshop.md
- Action: Verify whether 'workshop.md' should exist.

### 4. [HIGH] review_link_target
- **Target**: `action-type.md` — 6 issues
- Example: Wikilink target is unresolved: action-type.md
- Action: Verify whether 'action-type.md' should exist.

### 5. [HIGH] review_link_target
- **Target**: `link-type.md` — 5 issues
- Example: Wikilink target is unresolved: link-type.md
- Action: Verify whether 'link-type.md' should exist.

### 6. [HIGH] create_missing_research_doc
- **Target**: `research/vendor-comparison-matrix.md` — 4 issues
- Example: Wikilink target is unresolved: research/vendor-comparison-matrix.md
- Action: Verify whether 'research/vendor-comparison-matrix.md' should exist.

### 7. [HIGH] review_link_target
- **Target**: `property.md` — 4 issues
- Example: Wikilink target is unresolved: property.md
- Action: Verify whether 'property.md' should exist.

### 8. [HIGH] review_link_target
- **Target**: `inbox/信息化的基础认识.pdf.md` — 4 issues
- Example: Wikilink target is unresolved: inbox/信息化的基础认识.pdf.md
- Action: Verify whether 'inbox/信息化的基础认识.pdf.md' should exist.

### 9. [HIGH] review_link_target
- **Target**: `functions.md` — 3 issues
- Example: Wikilink target is unresolved: functions.md
- Action: Verify whether 'functions.md' should exist.

### 10. [HIGH] review_link_target
- **Target**: `b2b-product-bilateral-game.md` — 3 issues
- Example: Wikilink target is unresolved: b2b-product-bilateral-game.md
- Action: Verify whether 'b2b-product-bilateral-game.md' should exist.

### 11. [HIGH] review_link_target
- **Target**: `mcp.md` — 3 issues
- Example: Wikilink target is unresolved: mcp.md
- Action: Verify whether 'mcp.md' should exist.

### 12. [HIGH] review_link_target
- **Target**: `osdk.md` — 3 issues
- Example: Wikilink target is unresolved: osdk.md
- Action: Verify whether 'osdk.md' should exist.

### 13. [HIGH] review_link_target
- **Target**: `aip.md` — 3 issues
- Example: Wikilink target is unresolved: aip.md
- Action: Verify whether 'aip.md' should exist.

### 14. [HIGH] update_eval_gold_doc_id
- **Target**: `cases/banking-knowledge-graph-customer-360` — 1 issues
- Example: Questions: C2
- Action: Add 'cases/banking-knowledge-graph-customer-360.md' or update eval gold IDs.

### 15. [HIGH] update_eval_gold_doc_id
- **Target**: `cases/healthcare-ontology-patient-modeling` — 1 issues
- Example: Questions: C3
- Action: Add 'cases/healthcare-ontology-patient-modeling.md' or update eval gold IDs.

### By Action

| Action | Count |
|--------|-------|
| review_link_target | 30 |
| update_eval_gold_doc_id | 7 |
| create_missing_research_doc | 2 |

## Persistence

- Rescan: 97 confirmed, 0 pending — triage persisted: ✅

## Boundaries

- ✅ External KB not modified
- ✅ No auto-fix of KB files
- ✅ No Graph RAG / graph DB
- ✅ No Agent auto-write
- ✅ Curation backlog is human action guidance only

## Next

- Phase 10.3 Ontology graph UX polish