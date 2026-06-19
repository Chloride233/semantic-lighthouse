# Ontology Model Package Demo Report

**Date**: 2026-06-19
**Group**: Ontology Curation Demo (bf5f3696-a775-46f1-9133-949b5a3fa501)

## Selected Drafts

| Type | Name |
|------|------|
| object_type | Case |
| object_type | Concept |
| property | Concept.tags |
| link_type | Concept -> Case (wikilink) |
| action_type | Review Link Target |

## Quality Gate
  Errors: 0, Warnings: 4

| Code | Count |
|------|-------|
| governance_action_candidate | 1 |
| knowledge_meta_model_candidate | 2 |
| untyped_wikilink_candidate | 1 |

## Package
- Version: 1, Hash: `2a8a7d137065d402dbfcdc1689829c3d7471172790510972297c27f037a050c4`
- Drafts: 5, Quality: WARN
- OT=2, Prop=1, Link=1, Action=1
- Action contract: required_role=admin, confirmation=always, evidence=['ontology_validation_issue']

## Idempotency & Hash
- Same accepted set → same package (idempotent)
- SHA-256 matches stored content_hash

## Audit Chain
- Shared review service accepted all 5 drafts
- All accepted drafts: reviewed_by, reviewed_at, review_note
- Package: created_by, created_at
- 71 unselected drafts unchanged

## Boundaries
- No external KB modification / Agent / LLM / publish / execution
- Accepted ≠ production; package is immutable snapshot
