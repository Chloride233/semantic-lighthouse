"""Ontology scan service — frontmatter validation and entity read model extraction.

Phase 9.1 + 9.2: validates Document.frontmatter against the knowledge-base schema,
generates OntologyEntity and OntologyValidationIssue records.

Read-only governance: does NOT modify external KB files.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from semantic_lighthouse.models import (
    Document,
    OntologyEntity,
    OntologyValidationIssue,
)

ENTITY_TYPES = {
    "Concept", "Vendor", "Product", "Methodology", "Case",
    "Person", "Research", "Proposal", "FAQ",
}
DOCUMENT_TYPES = {
    "Schema", "Index", "AutoIndex", "Roadmap", "Changelog", "Template",
}
STATUS_VALUES = {"stub", "draft", "reviewed", "canonical"}
SOURCE_VALUES = {
    "official-doc", "market-research", "public-article",
    "case-report", "personal-analysis",
}


def _issue(
    group_id: str,
    document_id: str,
    severity: str,
    code: str,
    message: str,
    source_path: str,
    entity_id: str | None = None,
    field: str | None = None,
    details: dict | None = None,
) -> OntologyValidationIssue:
    return OntologyValidationIssue(
        group_id=group_id,
        document_id=document_id,
        entity_id=entity_id,
        severity=severity,
        code=code,
        field=field,
        message=message,
        source_path=source_path,
        details=details or {},
    )


def scan_group(db: Session, group_id: str) -> dict:
    """Scan all ready documents in a group, rebuild entities and issues.

    Returns dict with scanned_count, entity_count, issue_count.
    """
    docs = db.scalars(
        select(Document).where(
            Document.group_id == group_id,
            Document.status == "ready",
        )
    ).all()

    # Clear existing ontology data for this group (rebuild each scan)
    for issue in db.scalars(
        select(OntologyValidationIssue).where(
            OntologyValidationIssue.group_id == group_id,
        )
    ).all():
        db.delete(issue)

    for entity in db.scalars(
        select(OntologyEntity).where(OntologyEntity.group_id == group_id)
    ).all():
        db.delete(entity)

    db.flush()

    issues: list[OntologyValidationIssue] = []
    entities: list[OntologyEntity] = []

    for doc in docs:
        fm = doc.frontmatter if isinstance(doc.frontmatter, dict) else {}
        sp = doc.source_path or ""

        entity_type = fm.get("entityType")
        document_type = fm.get("documentType")
        has_entity = entity_type is not None
        has_doc = document_type is not None

        # Type conflict
        if has_entity and has_doc:
            issues.append(_issue(
                group_id, doc.id, "error", "type_conflict",
                f"entityType={entity_type} and documentType={document_type} cannot coexist",
                sp, field="entityType",
                details={"entityType": entity_type, "documentType": document_type},
            ))
            continue

        # Document type document: validate but don't create entity
        if has_doc:
            if document_type not in DOCUMENT_TYPES:
                issues.append(_issue(
                    group_id, doc.id, "error", "invalid_document_type",
                    f"Unknown documentType: {document_type}",
                    sp, field="documentType",
                    details={"documentType": document_type, "allowed": sorted(DOCUMENT_TYPES)},
                ))
            continue

        # Entity type document
        if not has_entity:
            issues.append(_issue(
                group_id, doc.id, "error", "missing_entity_type",
                "entityType is required for knowledge entities",
                sp,
            ))
            continue

        if entity_type not in ENTITY_TYPES:
            issues.append(_issue(
                group_id, doc.id, "error", "invalid_entity_type",
                f"Unknown entityType: {entity_type}",
                sp, field="entityType",
                details={"entityType": entity_type, "allowed": sorted(ENTITY_TYPES)},
            ))
            continue

        # Required fields
        tags = fm.get("tags")
        created = fm.get("created")
        if not tags:
            issues.append(_issue(
                group_id, doc.id, "warning", "missing_required_field",
                "tags is required", sp, field="tags",
            ))
        if not created:
            issues.append(_issue(
                group_id, doc.id, "warning", "missing_required_field",
                "created date is required", sp, field="created",
            ))

        # Tags must be a list of strings
        clean_tags: list = []
        tags_valid = True
        if tags is not None:
            if not isinstance(tags, list):
                issues.append(_issue(
                    group_id, doc.id, "warning", "invalid_list_field",
                    f"tags must be a list, got {type(tags).__name__}",
                    sp, field="tags",
                    details={"value": str(tags)[:200]},
                ))
                tags_valid = False
            else:
                for i, t in enumerate(tags):
                    if not isinstance(t, str):
                        issues.append(_issue(
                            group_id, doc.id, "warning", "invalid_list_field",
                            f"tags[{i}] must be string, got {type(t).__name__}",
                            sp, field="tags",
                            details={"index": i, "value": str(t)[:200]},
                        ))
                        tags_valid = False
                if tags_valid:
                    clean_tags = tags

        # Aliases must be a list of strings if present
        aliases_raw = fm.get("aliases")
        clean_aliases: list = []
        if aliases_raw is not None:
            if not isinstance(aliases_raw, list):
                issues.append(_issue(
                    group_id, doc.id, "warning", "invalid_list_field",
                    f"aliases must be a list, got {type(aliases_raw).__name__}",
                    sp, field="aliases",
                    details={"value": str(aliases_raw)[:200]},
                ))
            else:
                aliases_valid = True
                for i, a in enumerate(aliases_raw):
                    if not isinstance(a, str):
                        issues.append(_issue(
                            group_id, doc.id, "warning", "invalid_list_field",
                            f"aliases[{i}] must be string, got {type(a).__name__}",
                            sp, field="aliases",
                            details={"index": i, "value": str(a)[:200]},
                        ))
                        aliases_valid = False
                if aliases_valid:
                    clean_aliases = aliases_raw

        # Controlled vocabulary: status
        status_val = fm.get("status")
        clean_status = None
        if status_val is not None:
            if status_val not in STATUS_VALUES:
                issues.append(_issue(
                    group_id, doc.id, "warning", "invalid_controlled_value",
                    f"Unknown status: {status_val}",
                    sp, field="status",
                    details={"status": status_val, "allowed": sorted(STATUS_VALUES)},
                ))
            else:
                clean_status = status_val

        # Controlled vocabulary: source
        source_val = fm.get("source")
        clean_source = None
        if source_val is not None:
            if source_val not in SOURCE_VALUES:
                issues.append(_issue(
                    group_id, doc.id, "warning", "invalid_controlled_value",
                    f"Unknown source: {source_val}",
                    sp, field="source",
                    details={"source": source_val, "allowed": sorted(SOURCE_VALUES)},
                ))
            else:
                clean_source = source_val

        # Create entity
        entity = OntologyEntity(
            group_id=group_id,
            document_id=doc.id,
            title=doc.title,
            entity_type=entity_type,
            aliases=clean_aliases,
            source_path=sp,
            source=clean_source,
            status=clean_status,
            tags=clean_tags,
        )
        db.add(entity)
        db.flush()  # get entity.id for issue linking

        entities.append(entity)

    db.add_all(issues)
    db.commit()

    return {
        "scanned_count": len(docs),
        "entity_count": len(entities),
        "issue_count": len(issues),
    }
