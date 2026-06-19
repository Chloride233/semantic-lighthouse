"""Ontology modeling draft generation — deterministic rules from existing ontology data.

Phase 11.3: generates Object Type / Property / Link Type / Action Type drafts
from group-scoped entities, relations, frontmatter, and governance issues.
No LLM, no Agent, no filesystem, no external KB modification.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from semantic_lighthouse.models import (
    Document,
    OntologyEntity,
    OntologyModelingDraft,
    OntologyRelation,
    OntologyValidationIssue,
)


def determine_action_type(code: str, triage_note: str) -> str:
    """Determine action type from issue code and triage note.

    Pure function — no DB, no side effects. Safe to call from anywhere.
    Moved from scripts/run_ontology_curation_demo.py so the draft generation
    service can use it without importing from scripts/.
    """
    if code == "stale_eval_gold_doc_id":
        return "update_eval_gold_doc_id"
    if code in ("duplicate_title", "duplicate_alias"):
        return "resolve_identity_conflict"
    if code == "unresolved_wikilink":
        if triage_note == "missing_research_doc_or_directory":
            return "create_missing_research_doc"
        if triage_note == "missing_or_renamed_entity_doc":
            return "create_or_rename_entity_doc"
        return "review_link_target"
    return "review_link_target"


# ── Generation constants ──────────────────────────────────────────────────

EXCLUDED_PROPERTY_FIELDS: set[str] = {"entityType", "documentType"}

ACTION_TYPE_NAMES: dict[str, str] = {
    "update_eval_gold_doc_id": "Update Eval Gold Document ID",
    "resolve_identity_conflict": "Resolve Identity Conflict",
    "create_missing_research_doc": "Create Missing Research Document",
    "create_or_rename_entity_doc": "Create or Rename Entity Document",
    "review_link_target": "Review Link Target",
}

MAX_EVIDENCE_SAMPLES = 20


# ── Main generation function ──────────────────────────────────────────────


def generate_modeling_drafts(
    db: Session,
    group_id: str,
    created_by: str,
) -> dict[str, Any]:
    """Generate modeling drafts deterministically from group ontology data.

    Reads: OntologyEntity, OntologyRelation, OntologyValidationIssue, Document,
           and existing OntologyModelingDraft records for the group.

    Writes: new OntologyModelingDraft records (proposed status).

    Returns dict with generated_count, existing_count, skipped_count, counts_by_type.

    Idempotent: re-running with the same data produces no duplicates.
    Never modifies existing drafts (status, payload, review metadata).
    """
    # ── Load all source data ──────────────────────────────────────────
    entities = sorted(
        db.scalars(
            select(OntologyEntity).where(OntologyEntity.group_id == group_id)
        ).all(),
        key=lambda e: (e.source_path, e.id),
    )

    if not entities:
        return {
            "generated_count": 0,
            "existing_count": 0,
            "skipped_count": 0,
            "counts_by_type": {"object_type": 0, "property": 0, "link_type": 0, "action_type": 0},
        }

    entity_by_id: dict[str, OntologyEntity] = {e.id: e for e in entities}

    # Documents (for frontmatter → property drafts)
    doc_ids = {e.document_id for e in entities}
    docs: dict[str, Document] = {}
    if doc_ids:
        for doc in db.scalars(select(Document).where(Document.id.in_(doc_ids))).all():
            docs[doc.id] = doc

    # Resolved relations only (must have target_entity_id)
    relations = sorted(
        db.scalars(
            select(OntologyRelation).where(
                OntologyRelation.group_id == group_id,
                OntologyRelation.status == "resolved",
                OntologyRelation.target_entity_id.isnot(None),
            )
        ).all(),
        key=lambda r: (
            r.source_document_id,
            r.target_path,
            r.target_label or "",
            r.relation_type,
        ),
    )

    # Confirmed issues only
    issues = sorted(
        db.scalars(
            select(OntologyValidationIssue).where(
                OntologyValidationIssue.group_id == group_id,
                OntologyValidationIssue.triage_status == "confirmed",
            )
        ).all(),
        key=lambda i: (i.code, i.issue_key or ""),
    )

    # ── Build existing draft index ─────────────────────────────────────
    existing_keys: set[str] = set()
    existing_type_names: set[tuple[str, str]] = set()
    for d in db.scalars(
        select(OntologyModelingDraft).where(
            OntologyModelingDraft.group_id == group_id,
        )
    ).all():
        gen_key = (d.payload or {}).get("generation_key")
        if gen_key:
            existing_keys.add(gen_key)
        existing_type_names.add((d.draft_type, (d.name or "").strip().casefold()))

    new_drafts: list[OntologyModelingDraft] = []
    counts: dict[str, int] = {"object_type": 0, "property": 0, "link_type": 0, "action_type": 0}
    existing = 0
    skipped = 0

    # ── Object Type drafts ─────────────────────────────────────────────
    type_entities: dict[str, list[OntologyEntity]] = defaultdict(list)
    for e in entities:
        type_entities[e.entity_type].append(e)

    for entity_type in sorted(type_entities):
        type_ents = type_entities[entity_type]
        gen_key = f"object_type:{entity_type.strip().casefold()}"
        normalized_name = entity_type.strip().casefold()

        if gen_key in existing_keys or ("object_type", normalized_name) in existing_type_names:
            existing += 1
            continue

        first = type_ents[0]
        evidence = _build_entity_evidence(type_ents[:MAX_EVIDENCE_SAMPLES])

        payload = {
            "generator": "deterministic_v1",
            "generation_key": gen_key,
            "source_entity_type": entity_type,
            "entity_count": len(type_ents),
        }

        description = (
            f"Candidate object type derived from governed knowledge entity type "
            f"'{entity_type}'. Based on {len(type_ents)} entities. "
            f"This is NOT a production Object Type."
        )

        new_drafts.append(OntologyModelingDraft(
            group_id=group_id,
            draft_type="object_type",
            name=entity_type,
            description=description,
            status="proposed",
            source_entity_id=first.id,
            evidence_refs=evidence,
            payload=payload,
            created_by=created_by,
        ))
        existing_keys.add(gen_key)
        existing_type_names.add(("object_type", normalized_name))
        counts["object_type"] += 1

    # ── Property drafts ────────────────────────────────────────────────
    # Group by (entity_type, frontmatter_field)
    fields_by_type: dict[str, dict[str, list[tuple[OntologyEntity, Any]]]] = defaultdict(
        lambda: defaultdict(list)
    )

    for e in entities:
        doc = docs.get(e.document_id)
        if not doc or not isinstance(doc.frontmatter, dict):
            continue
        for field, value in doc.frontmatter.items():
            if field in EXCLUDED_PROPERTY_FIELDS:
                continue
            if not field or not field.strip():
                skipped += 1
                continue
            fields_by_type[e.entity_type][field].append((e, value))

    for entity_type in sorted(fields_by_type):
        for field in sorted(fields_by_type[entity_type]):
            entries = fields_by_type[entity_type][field]
            if not entries:
                continue

            gen_key = f"property:{entity_type.strip().casefold()}:{field.strip().casefold()}"
            name = f"{entity_type}.{field}"
            normalized_name = name.strip().casefold()

            if gen_key in existing_keys or ("property", normalized_name) in existing_type_names:
                existing += 1
                continue

            first_entity = entries[0][0]
            observed_types = sorted(set(type(v).__name__ for _, v in entries))
            entity_ids_in_group = sorted({e.id for e, _ in entries})

            evidence = _build_entity_evidence(
                [e for e, _ in entries[:MAX_EVIDENCE_SAMPLES]]
            )

            payload = {
                "generator": "deterministic_v1",
                "generation_key": gen_key,
                "object_type": entity_type,
                "property_name": field,
                "observed_value_types": observed_types,
                "observed_count": len(entries),
                "entity_count": len(entity_ids_in_group),
            }

            description = (
                f"Candidate property derived from frontmatter field '{field}' "
                f"of entity type '{entity_type}'. "
                f"Observed in {len(entries)} instances across "
                f"{len(entity_ids_in_group)} entities. "
                f"This is NOT a production Property."
            )

            new_drafts.append(OntologyModelingDraft(
                group_id=group_id,
                draft_type="property",
                name=name,
                description=description,
                status="proposed",
                source_entity_id=first_entity.id,
                evidence_refs=evidence,
                payload=payload,
                created_by=created_by,
            ))
            existing_keys.add(gen_key)
            existing_type_names.add(("property", normalized_name))
            counts["property"] += 1

    # ── Link Type drafts ───────────────────────────────────────────────
    # Group resolved relations by (source_entity_type, relation_type, target_entity_type)
    type_rel_groups: dict[tuple[str, str, str], list[OntologyRelation]] = defaultdict(list)
    for rel in relations:
        src_entity = entity_by_id.get(rel.source_entity_id)
        tgt_entity = entity_by_id.get(rel.target_entity_id) if rel.target_entity_id else None
        if not src_entity or not tgt_entity:
            skipped += 1
            continue
        key = (src_entity.entity_type, rel.relation_type, tgt_entity.entity_type)
        type_rel_groups[key].append(rel)

    for (src_type, rel_type, tgt_type) in sorted(type_rel_groups):
        rels = type_rel_groups[(src_type, rel_type, tgt_type)]
        gen_key = (
            f"link_type:{src_type.strip().casefold()}:"
            f"{rel_type.strip().casefold()}:{tgt_type.strip().casefold()}"
        )
        name = f"{src_type} -> {tgt_type} ({rel_type})"
        normalized_name = name.strip().casefold()

        if gen_key in existing_keys or ("link_type", normalized_name) in existing_type_names:
            existing += 1
            continue

        first_rel = rels[0]
        evidence = _build_relation_evidence(rels[:MAX_EVIDENCE_SAMPLES])

        payload = {
            "generator": "deterministic_v1",
            "generation_key": gen_key,
            "source_object_type": src_type,
            "target_object_type": tgt_type,
            "relation_type": rel_type,
            "relation_count": len(rels),
        }

        description = (
            f"Candidate link type derived from resolved wikilink relations "
            f"between '{src_type}' and '{tgt_type}'. "
            f"Based on {len(rels)} relations. "
            f"This is NOT a production Link Type."
        )

        new_drafts.append(OntologyModelingDraft(
            group_id=group_id,
            draft_type="link_type",
            name=name,
            description=description,
            status="proposed",
            source_relation_id=first_rel.id,
            evidence_refs=evidence,
            payload=payload,
            created_by=created_by,
        ))
        existing_keys.add(gen_key)
        existing_type_names.add(("link_type", normalized_name))
        counts["link_type"] += 1

    # ── Action Type drafts ─────────────────────────────────────────────
    # Group confirmed issues by action_type (via determine_action_type)
    action_type_issues: dict[str, list[OntologyValidationIssue]] = defaultdict(list)
    for issue in issues:
        at = determine_action_type(issue.code, issue.triage_note or "")
        action_type_issues[at].append(issue)

    for action_type in sorted(action_type_issues):
        iss_list = action_type_issues[action_type]
        gen_key = f"action_type:{action_type}"
        name = ACTION_TYPE_NAMES.get(action_type, action_type)
        normalized_name = name.strip().casefold()

        if gen_key in existing_keys or ("action_type", normalized_name) in existing_type_names:
            existing += 1
            continue

        first_issue = iss_list[0]
        issue_codes = sorted({i.code for i in iss_list})

        evidence = _build_issue_evidence(iss_list[:MAX_EVIDENCE_SAMPLES])

        payload = {
            "generator": "deterministic_v1",
            "generation_key": gen_key,
            "scope": "ontology_governance",
            "issue_count": len(iss_list),
            "issue_codes": issue_codes,
        }

        description = (
            f"Human governance action candidate of type '{action_type}'. "
            f"Based on {len(iss_list)} confirmed governance issues "
            f"(codes: {', '.join(issue_codes)}). "
            f"This is NOT an automatically executable action."
        )

        new_drafts.append(OntologyModelingDraft(
            group_id=group_id,
            draft_type="action_type",
            name=name,
            description=description,
            status="proposed",
            source_issue_id=first_issue.id,
            evidence_refs=evidence,
            payload=payload,
            created_by=created_by,
        ))
        existing_keys.add(gen_key)
        existing_type_names.add(("action_type", normalized_name))
        counts["action_type"] += 1

    # ── Persist ────────────────────────────────────────────────────────
    for draft in new_drafts:
        db.add(draft)
    db.commit()

    return {
        "generated_count": len(new_drafts),
        "existing_count": existing,
        "skipped_count": skipped,
        "counts_by_type": counts,
    }


# ── Evidence helpers ──────────────────────────────────────────────────────


def _build_entity_evidence(entities: list[OntologyEntity]) -> list[dict[str, Any]]:
    """Build evidence_refs list from entity samples."""
    return [
        {
            "entity_id": e.id,
            "document_id": e.document_id,
            "source_path": e.source_path,
            "title": e.title,
        }
        for e in entities
    ]


def _build_relation_evidence(relations: list[OntologyRelation]) -> list[dict[str, Any]]:
    """Build evidence_refs list from relation samples."""
    return [
        {
            "relation_id": r.id,
            "source_entity_id": r.source_entity_id,
            "target_entity_id": r.target_entity_id,
            "target_path": r.target_path,
            "target_label": r.target_label,
            "source_document_id": r.source_document_id,
        }
        for r in relations
    ]


def _build_issue_evidence(issues: list[OntologyValidationIssue]) -> list[dict[str, Any]]:
    """Build evidence_refs list from issue samples."""
    return [
        {
            "issue_id": i.id,
            "code": i.code,
            "issue_key": i.issue_key,
            "source_path": i.source_path,
            "message": i.message,
        }
        for i in issues
    ]
