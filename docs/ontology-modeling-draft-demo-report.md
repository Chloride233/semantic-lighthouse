# Ontology Modeling Draft Demo Report

**Date**: 2026-06-19
**Phase**: 12.1 real KB modeling draft demo
**DB**: `sqlite+pysqlite:///.tmp/phase12-modeling-demo.db`
**Group**: `Ontology Curation Demo` (`a00f1fcb-5e84-417b-9cbb-7eee8ad98c63`)

## 1. Source Baseline

| Metric | Count |
|--------|-------|
| Entities | 74 |
| Relations | 186 |
| Issues (total) | 97 |
| Issues (confirmed) | 97 |

## 2. Draft Counts

| Draft Type | Count |
|------------|-------|
| object_type | 8 |
| property | 48 |
| link_type | 17 |
| action_type | 3 |
| **Total** | **76** |

First generation: 76 generated, 0 existing, 0 skipped.

## 3. Hard Quality Checks

| Check | Count | Gate |
|-------|-------|------|
| Missing generation_key | 0 | must be 0 |
| Missing source pointer | 0 | must be 0 |
| Empty evidence_refs | 0 | must be 0 |
| Duplicate (type, name) | 0 | must be 0 |
| Second generation idempotent | YES | must be YES |

**Technical integrity**: **PASS**

## 4. Noise Indicators

| Indicator | Count | Note |
|-----------|-------|------|
| Property candidates with 1 entity | 19 | single-entity candidates carry less signal |
| Link candidates with 1 relation evidence | 5 | single-relation candidates carry less signal |
| Action candidates with 1 issue evidence | 0 | single-issue candidates carry less signal |

### Properties per Object Type

| Object Type | Property Count |
|-------------|---------------|
| Proposal | 10 |
| Case | 9 |
| Concept | 5 |
| Methodology | 5 |
| Person | 5 |
| Product | 5 |
| Vendor | 5 |
| FAQ | 4 |

## 5. Candidate Samples

### Object Type (showing 8 of 8)

| Name | Source | Evidence | Key Payload |
|------|--------|----------|-------------|
| Concept | d4e88f4a... | 20 | key=object_type:concept, entities=44 |
| Case | b5ffe6b3... | 12 | key=object_type:case, entities=12 |
| Vendor | f6aff2ab... | 8 | key=object_type:vendor, entities=8 |
| Product | e897a444... | 4 | key=object_type:product, entities=4 |
| Methodology | 272fbb3f... | 3 | key=object_type:methodology, entities=3 |
| FAQ | 4874db9f... | 1 | key=object_type:faq, entities=1 |
| Person | a125dce1... | 1 | key=object_type:person, entities=1 |
| Proposal | aa790016... | 1 | key=object_type:proposal, entities=1 |

### Property (showing 10 of 48)

| Name | Source | Evidence | Key Payload |
|------|--------|----------|-------------|
| Concept.aliases | d4e88f4a... | 20 | key=property:concept:aliases, types=['list'] |
| Concept.created | d4e88f4a... | 20 | key=property:concept:created, types=['str'] |
| Concept.source | d4e88f4a... | 20 | key=property:concept:source, types=['str'] |
| Concept.status | d4e88f4a... | 20 | key=property:concept:status, types=['str'] |
| Concept.tags | d4e88f4a... | 20 | key=property:concept:tags, types=['list'] |
| Case.concepts | b5ffe6b3... | 12 | key=property:case:concepts, types=['list'] |
| Case.created | b5ffe6b3... | 12 | key=property:case:created, types=['str'] |
| Case.industry | b5ffe6b3... | 12 | key=property:case:industry, types=['list'] |
| Case.scale | b5ffe6b3... | 12 | key=property:case:scale, types=['list', 'str'] |
| Case.scenario | b5ffe6b3... | 12 | key=property:case:scenario, types=['list'] |

### Link Type (showing 10 of 17)

| Name | Source | Evidence | Key Payload |
|------|--------|----------|-------------|
| Case -> Concept (wikilink) | af02640b... | 20 | key=link_type:case:wikilink:concept, rels=39 |
| Concept -> Case (wikilink) | fa625fb4... | 11 | key=link_type:concept:wikilink:case, rels=11 |
| Methodology -> Concept (wikilink) | 9313b1b8... | 10 | key=link_type:methodology:wikilink:concept, rels=10 |
| Case -> Vendor (wikilink) | 055c10ab... | 8 | key=link_type:case:wikilink:vendor, rels=8 |
| FAQ -> Concept (wikilink) | 951bdd65... | 4 | key=link_type:faq:wikilink:concept, rels=4 |
| Methodology -> Case (wikilink) | c0b28caf... | 4 | key=link_type:methodology:wikilink:case, rels=4 |
| Proposal -> Concept (wikilink) | f3c4b767... | 4 | key=link_type:proposal:wikilink:concept, rels=4 |
| FAQ -> Methodology (wikilink) | e4cc3bec... | 3 | key=link_type:faq:wikilink:methodology, rels=3 |
| Case -> Methodology (wikilink) | d1b2a535... | 2 | key=link_type:case:wikilink:methodology, rels=2 |
| Concept -> Methodology (wikilink) | b9c39696... | 2 | key=link_type:concept:wikilink:methodology, rels=2 |

### Action Type (showing 3 of 3)

| Name | Source | Evidence | Key Payload |
|------|--------|----------|-------------|
| Review Link Target | 468b91d1... | 20 | key=action_type:review_link_target, issues=85 |
| Update Eval Gold Document ID | 9b9b153c... | 7 | key=action_type:update_eval_gold_doc_id, issues=7 |
| Create Missing Research Document | 033de4d2... | 5 | key=action_type:create_missing_research_doc, issues=5 |

## 6. Interpretation

### What These Candidates Are

- **Object Type candidates** are derived from knowledge base `entityType` values (Concept, Vendor, Product, Methodology, Case, Person, Proposal, FAQ). They are **knowledge meta-model candidates** — they describe how the KB is structured, not necessarily customer business objects. A `Concept` object type should not be confused with a customer-facing business object type.
- **Property candidates** are derived from frontmatter fields per entity type. They describe KB metadata conventions (e.g., `Concept.tags`, `Vendor.created`), not necessarily business object properties.
- **Link Type candidates** are derived from `[[wikilink]]` relations between entities. They represent **knowledge association patterns**, not business semantic relationships. A `Concept -> Concept (wikilink)` link type means two KB concept documents reference each other; it does not imply a business domain relationship.
- **Action Type candidates** are derived from governance issue codes and triage rules. They are **human governance action suggestions**, not automatically executable business actions. `review_link_target` means a human should review a broken wikilink; it does not trigger an automated workflow.

### Important Distinctions

- **proposed ≠ accepted ≠ production**. All drafts here are `proposed` — none have been reviewed by a human owner/admin.
- **Knowledge meta-model ≠ business ontology**. The current KB entityType taxonomy (Concept/Vendor/Product/etc.) is a document classification system. Direct 1:1 mapping to business object types requires domain modeling from a human expert.
- **wikilink ≠ business relation**. Wikilinks express navigational/document connections, not typed business relationships with cardinality, direction, and lifecycle semantics.
- **governance action ≠ executable action**. Action type drafts describe what governance tasks exist; they do not define automated business operations with roles, inputs, outputs, and side effects.

## 7. Quality Conclusion

**Technical integrity: PASS** — all hard checks are 0, generation is idempotent.

Noise indicators: 19 single-entity properties, 5 single-relation links, 0 single-issue actions. These are risk flags, not failures — they indicate candidates with weaker evidence that a human reviewer should scrutinize more carefully.

**Recommendation**: Proceed to Phase 12.2 (draft quality gates). The deterministic generation pipeline is producing structurally valid, idempotent, evidence-backed candidates. Quality gates in 12.2 should add per-draft validation before accepting any draft for package assembly.

## 8. Boundaries

- ✅ No drafts accepted or rejected — all remain `proposed`
- ✅ No external KB modified
- ✅ No Agent, no LLM, no web calls
- ✅ No new migration, no API changes
- ✅ Generation is deterministic and idempotent
- ✅ Accepted ≠ production — this demo does not publish anything
