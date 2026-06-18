"""Ontology governance router — scan, entity list, validation issues, relations.

Phase 9.1–9.3: read-only governance. No external KB modification.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from semantic_lighthouse.database import get_db
from semantic_lighthouse.dependencies import (
    get_current_user,
    get_membership_or_404,
    require_group_role,
)
from semantic_lighthouse.models import (
    OntologyEntity,
    OntologyRelation,
    OntologyValidationIssue,
    User,
    utc_now,
)
from semantic_lighthouse.schemas import (
    OntologyEntityListResponse,
    OntologyEntityResponse,
    OntologyIssueListResponse,
    OntologyIssueTriageRequest,
    OntologyRelationListResponse,
    OntologyRelationResponse,
    OntologyScanResponse,
    OntologyValidationIssueResponse,
)
from semantic_lighthouse.services.ontology import scan_group

router = APIRouter(prefix="/groups/{group_id}/ontology", tags=["ontology"])


# ── scan ──────────────────────────────────────────────────────────────


@router.post("/scan", response_model=OntologyScanResponse)
def scan_ontology(
    group_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OntologyScanResponse:
    """Run frontmatter validation and entity extraction. Owner or admin only."""
    require_group_role(db, current_user.id, group_id, {"owner", "admin"})
    result = scan_group(db, group_id)
    return OntologyScanResponse(**result)


# ── entities ──────────────────────────────────────────────────────────


@router.get("/entities", response_model=OntologyEntityListResponse)
def list_entities(
    group_id: str,
    entity_type: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    q: str | None = Query(default=None, description="Search title"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OntologyEntityListResponse:
    """List group-scoped ontology entities. Any member can read."""
    get_membership_or_404(db, current_user.id, group_id)

    base = select(OntologyEntity).where(OntologyEntity.group_id == group_id)
    if entity_type:
        base = base.where(OntologyEntity.entity_type == entity_type)
    if status_filter:
        base = base.where(OntologyEntity.status == status_filter)
    if q:
        base = base.where(OntologyEntity.title.ilike(f"%{q}%"))

    total = db.scalar(select(func.count()).select_from(base.subquery()))
    rows = db.scalars(
        base.order_by(OntologyEntity.title.asc()).offset(offset).limit(limit)
    ).all()

    return OntologyEntityListResponse(
        entities=[_entity_response(e) for e in rows],
        total=total or 0,
    )


# ── issues ────────────────────────────────────────────────────────────


@router.get("/issues", response_model=OntologyIssueListResponse)
def list_issues(
    group_id: str,
    severity: str | None = Query(default=None),
    code: str | None = Query(default=None),
    triage_status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OntologyIssueListResponse:
    """List group-scoped validation issues. Any member can read."""
    get_membership_or_404(db, current_user.id, group_id)

    base = select(OntologyValidationIssue).where(
        OntologyValidationIssue.group_id == group_id
    )
    if severity:
        base = base.where(OntologyValidationIssue.severity == severity)
    if code:
        base = base.where(OntologyValidationIssue.code == code)
    if triage_status:
        base = base.where(OntologyValidationIssue.triage_status == triage_status)

    total = db.scalar(select(func.count()).select_from(base.subquery()))
    rows = db.scalars(
        base.order_by(OntologyValidationIssue.created_at.desc())
        .offset(offset)
        .limit(limit)
    ).all()

    return OntologyIssueListResponse(
        issues=[_issue_response(i) for i in rows],
        total=total or 0,
    )


# ── triage ──────────────────────────────────────────────────────────


@router.post("/issues/{issue_id}/triage", response_model=OntologyValidationIssueResponse)
def triage_issue(
    group_id: str,
    issue_id: str,
    body: OntologyIssueTriageRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OntologyValidationIssueResponse:
    """Set triage status on a governance issue. Owner or admin only."""
    require_group_role(db, current_user.id, group_id, {"owner", "admin"})

    issue = db.scalar(
        select(OntologyValidationIssue).where(
            OntologyValidationIssue.id == issue_id,
            OntologyValidationIssue.group_id == group_id,
        )
    )
    if issue is None:
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found")

    issue.triage_status = body.triage_status
    issue.triage_note = body.triage_note or None
    issue.triaged_by = current_user.id
    issue.triaged_at = utc_now()
    db.commit()
    db.refresh(issue)
    return _issue_response(issue)


# ── relations ────────────────────────────────────────────────────────


@router.get("/relations", response_model=OntologyRelationListResponse)
def list_relations(
    group_id: str,
    status_filter: str | None = Query(default=None, alias="status"),
    source_entity_id: str | None = Query(default=None),
    target_entity_id: str | None = Query(default=None),
    relation_type: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OntologyRelationListResponse:
    """List group-scoped ontology relations. Any member can read."""
    get_membership_or_404(db, current_user.id, group_id)

    base = select(OntologyRelation).where(OntologyRelation.group_id == group_id)
    if status_filter:
        base = base.where(OntologyRelation.status == status_filter)
    if source_entity_id:
        base = base.where(OntologyRelation.source_entity_id == source_entity_id)
    if target_entity_id:
        base = base.where(OntologyRelation.target_entity_id == target_entity_id)
    if relation_type:
        base = base.where(OntologyRelation.relation_type == relation_type)

    total = db.scalar(select(func.count()).select_from(base.subquery()))
    rows = db.scalars(
        base.order_by(OntologyRelation.created_at.desc())
        .offset(offset)
        .limit(limit)
    ).all()

    return OntologyRelationListResponse(
        relations=[_relation_response(r) for r in rows],
        total=total or 0,
    )


# ── helpers ───────────────────────────────────────────────────────────


def _relation_response(r: OntologyRelation) -> OntologyRelationResponse:
    return OntologyRelationResponse(
        id=r.id,
        group_id=r.group_id,
        source_entity_id=r.source_entity_id,
        source_document_id=r.source_document_id,
        target_entity_id=r.target_entity_id,
        target_path=r.target_path,
        target_label=r.target_label,
        relation_type=r.relation_type,
        status=r.status,
        evidence_document_id=r.evidence_document_id,
        created_at=r.created_at,
    )


def _entity_response(e: OntologyEntity) -> OntologyEntityResponse:
    return OntologyEntityResponse(
        id=e.id,
        group_id=e.group_id,
        document_id=e.document_id,
        title=e.title,
        entity_type=e.entity_type,
        aliases=e.aliases,
        source_path=e.source_path,
        source=e.source,
        status=e.status,
        tags=e.tags,
        created_at=e.created_at,
        updated_at=e.updated_at,
    )


def _issue_response(i: OntologyValidationIssue) -> OntologyValidationIssueResponse:
    return OntologyValidationIssueResponse(
        id=i.id,
        group_id=i.group_id,
        document_id=i.document_id,
        entity_id=i.entity_id,
        severity=i.severity,
        code=i.code,
        field=i.field,
        message=i.message,
        source_path=i.source_path,
        details=i.details,
        created_at=i.created_at,
        issue_key=i.issue_key,
        triage_status=i.triage_status,
        triaged_by=i.triaged_by,
        triaged_at=i.triaged_at,
        triage_note=i.triage_note,
    )
