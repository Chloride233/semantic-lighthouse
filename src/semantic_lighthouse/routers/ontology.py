"""Ontology governance router — scan, entity list, validation issues, relations, modeling drafts.

Phase 9.1–9.3: read-only governance. No external KB modification.
Phase 11.1–11.2: modeling drafts read model — group-scoped, permission-aware.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
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
    OntologyModelingDraft,
    OntologyRelation,
    OntologyValidationIssue,
    RagRun,
    User,
    utc_now,
)
from semantic_lighthouse.schemas import (
    DRAFT_TYPES,
    DraftGenerationResponse,
    OntologyEntityListResponse,
    OntologyEntityResponse,
    OntologyIssueListResponse,
    OntologyIssueTriageRequest,
    OntologyDraftQualityResponse,
    OntologyModelingDraftBatchReviewRequest,
    OntologyModelingDraftBatchReviewResponse,
    OntologyModelingDraftCreateRequest,
    OntologyModelingDraftListResponse,
    OntologyModelingDraftResponse,
    OntologyModelingDraftReviewRequest,
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


# ── Phase 11 modeling drafts ───────────────────────────────────────────


@router.get("/drafts", response_model=OntologyModelingDraftListResponse)
def list_drafts(
    group_id: str,
    draft_type: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    source_entity_id: str | None = Query(default=None),
    q: str | None = Query(default=None, description="Search name"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OntologyModelingDraftListResponse:
    """List group-scoped modeling drafts. Any member can read."""
    get_membership_or_404(db, current_user.id, group_id)

    base = select(OntologyModelingDraft).where(
        OntologyModelingDraft.group_id == group_id
    )
    if draft_type:
        base = base.where(OntologyModelingDraft.draft_type == draft_type)
    if status_filter:
        base = base.where(OntologyModelingDraft.status == status_filter)
    if source_entity_id:
        base = base.where(OntologyModelingDraft.source_entity_id == source_entity_id)
    if q:
        base = base.where(OntologyModelingDraft.name.ilike(f"%{q}%"))

    total = db.scalar(select(func.count()).select_from(base.subquery()))
    rows = db.scalars(
        base.order_by(OntologyModelingDraft.created_at.desc())
        .offset(offset)
        .limit(limit)
    ).all()

    return OntologyModelingDraftListResponse(
        drafts=[_draft_response(d) for d in rows],
        total=total or 0,
    )


@router.post(
    "/drafts",
    response_model=OntologyModelingDraftResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_draft(
    group_id: str,
    body: OntologyModelingDraftCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OntologyModelingDraftResponse:
    """Create a proposed modeling draft. Owner or admin only. Status always starts as proposed."""
    require_group_role(db, current_user.id, group_id, {"owner", "admin"})

    # Validate draft_type
    if body.draft_type not in DRAFT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid draft_type: {body.draft_type}. Allowed: {sorted(DRAFT_TYPES)}",
        )

    # At least one proper evidence pointer is required.
    # evidence_refs alone is NOT sufficient — it is supplemental metadata only.
    has_evidence = (
        body.source_entity_id
        or body.source_relation_id
        or body.source_issue_id
        or body.source_rag_run_id
    )
    if not has_evidence:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one source pointer (source_entity_id, source_relation_id, "
            "source_issue_id, source_rag_run_id) is required to create a draft. "
            "evidence_refs alone is not sufficient.",
        )

    # Validate all source ids belong to this group
    _validate_source_in_group(db, group_id, OntologyEntity, body.source_entity_id, "source_entity_id")
    _validate_source_in_group(db, group_id, OntologyRelation, body.source_relation_id, "source_relation_id")
    _validate_source_in_group(
        db, group_id, OntologyValidationIssue, body.source_issue_id, "source_issue_id"
    )
    _validate_source_in_group(db, group_id, RagRun, body.source_rag_run_id, "source_rag_run_id")

    draft = OntologyModelingDraft(
        group_id=group_id,
        draft_type=body.draft_type,
        name=body.name,
        description=body.description or "",
        status="proposed",
        source_entity_id=body.source_entity_id,
        source_relation_id=body.source_relation_id,
        source_issue_id=body.source_issue_id,
        source_rag_run_id=body.source_rag_run_id,
        evidence_refs=body.evidence_refs,
        payload=body.payload,
        created_by=current_user.id,
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return _draft_response(draft)


# ── Phase 11.3: deterministic draft generation ───────────────────────


@router.post("/drafts/generate", response_model=DraftGenerationResponse)
def generate_drafts(
    group_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DraftGenerationResponse:
    """Generate modeling drafts deterministically from existing ontology data.

    Owner or admin only. Idempotent — re-running with same data produces no duplicates.
    Never modifies existing drafts (status, payload, review metadata).
    """
    require_group_role(db, current_user.id, group_id, {"owner", "admin"})

    entity_count = db.scalar(
        select(func.count()).select_from(
            select(OntologyEntity).where(OntologyEntity.group_id == group_id).subquery()
        )
    ) or 0

    if entity_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No ontology entities found in this group. Run ontology scan first.",
        )

    from semantic_lighthouse.services.ontology_drafts import generate_modeling_drafts

    result = generate_modeling_drafts(db, group_id, current_user.id)
    return DraftGenerationResponse(**result)


# ── Phase 11.4: human review workflow ─────────────────────────────────


@router.post("/drafts/review-batch", response_model=OntologyModelingDraftBatchReviewResponse)
def review_drafts_batch(
    group_id: str,
    body: OntologyModelingDraftBatchReviewRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OntologyModelingDraftBatchReviewResponse:
    """Atomically accept or reject up to 100 proposed modeling drafts.

    Owner or admin only. All drafts must exist in this group and be in proposed status.
    If any draft is missing, cross-group, or already reviewed, the entire batch is rejected
    with no partial updates.
    """
    require_group_role(db, current_user.id, group_id, {"owner", "admin"})

    # Deduplicate while preserving order
    unique_ids = list(dict.fromkeys(body.draft_ids))

    # Fetch all drafts in one query — must all exist and belong to this group
    drafts = list(
        db.scalars(
            select(OntologyModelingDraft).where(
                OntologyModelingDraft.id.in_(unique_ids),
                OntologyModelingDraft.group_id == group_id,
            )
        ).all()
    )

    if len(drafts) != len(unique_ids):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or more drafts not found in this group",
        )

    # All must still be proposed
    already_reviewed = [d for d in drafts if d.status != "proposed"]
    if already_reviewed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="One or more drafts have already been reviewed",
        )

    cleaned_note = body.review_note.strip() if body.review_note else None
    now = utc_now()

    for draft in drafts:
        draft.status = body.status
        draft.reviewed_by = current_user.id
        draft.reviewed_at = now
        draft.review_note = cleaned_note
        draft.updated_at = now

    db.commit()

    return OntologyModelingDraftBatchReviewResponse(
        reviewed_count=len(drafts),
        status=body.status,
        draft_ids=[d.id for d in drafts],
        reviewed_by=current_user.id,
        reviewed_at=now,
    )


@router.post("/drafts/{draft_id}/review", response_model=OntologyModelingDraftResponse)
def review_draft(
    group_id: str,
    draft_id: str,
    body: OntologyModelingDraftReviewRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OntologyModelingDraftResponse:
    """Accept or reject a single proposed modeling draft.

    Owner or admin only. Only proposed drafts can be reviewed (one-time audit).
    Accepted and rejected drafts are final — no reopen, no overwrite.
    """
    require_group_role(db, current_user.id, group_id, {"owner", "admin"})

    draft = db.scalar(
        select(OntologyModelingDraft).where(
            OntologyModelingDraft.id == draft_id,
            OntologyModelingDraft.group_id == group_id,
        )
    )
    if draft is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Draft not found",
        )

    if draft.status != "proposed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Draft has already been reviewed",
        )

    cleaned_note = body.review_note.strip() if body.review_note else None
    now = utc_now()

    draft.status = body.status
    draft.reviewed_by = current_user.id
    draft.reviewed_at = now
    draft.review_note = cleaned_note
    draft.updated_at = now

    db.commit()
    db.refresh(draft)
    return _draft_response(draft)


# ── Phase 12.2b: draft quality gate ──────────────────────────────────


@router.get("/drafts/quality", response_model=OntologyDraftQualityResponse)
def get_draft_quality(
    group_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OntologyDraftQualityResponse:
    """Validate all modeling drafts in this group. Any member can read.

    Returns PASS/WARN/FAIL status with per-draft issues.
    Read-only — never modifies drafts, commits, or calls external systems.
    """
    get_membership_or_404(db, current_user.id, group_id)

    from semantic_lighthouse.services.ontology_draft_quality import (
        validate_modeling_drafts,
    )

    result = validate_modeling_drafts(db, group_id)
    return OntologyDraftQualityResponse(**result)


# ── helpers ───────────────────────────────────────────────────────────


def _validate_source_in_group(
    db: Session,
    group_id: str,
    model: type,
    source_id: str | None,
    field_name: str,
) -> None:
    """Validate that a source id exists and belongs to the given group. 404 if not found."""
    if source_id is None:
        return
    obj = db.get(model, source_id)
    if obj is None or getattr(obj, "group_id", None) != group_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{field_name} not found in this group",
        )


def _draft_response(d: OntologyModelingDraft) -> OntologyModelingDraftResponse:
    return OntologyModelingDraftResponse(
        id=d.id,
        group_id=d.group_id,
        draft_type=d.draft_type,
        name=d.name,
        description=d.description,
        status=d.status,
        source_entity_id=d.source_entity_id,
        source_relation_id=d.source_relation_id,
        source_issue_id=d.source_issue_id,
        source_rag_run_id=d.source_rag_run_id,
        evidence_refs=d.evidence_refs,
        payload=d.payload,
        created_by=d.created_by,
        created_at=d.created_at,
        updated_at=d.updated_at,
        reviewed_by=d.reviewed_by,
        reviewed_at=d.reviewed_at,
        review_note=d.review_note,
    )


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
