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
    BusinessProject,
    DatasetAsset,
    OntologyEntity,
    OntologyModelingDraft,
    OntologyModelPackage,
    OntologyRelation,
    OntologyValidationIssue,
    RagRun,
    User,
    utc_now,
)
from semantic_lighthouse.schemas import (
    BusinessContractManifestResponse,
    DRAFT_TYPES,
    DatasetModelingResponse,
    DraftGenerationResponse,
    ProjectPackageBuildRequest,
    OntologyEntityListResponse,
    OntologyEntityResponse,
    OntologyIssueListResponse,
    OntologyIssueTriageRequest,
    OntologyDraftQualityResponse,
    OntologyModelPackageBuildResponse,
    OntologyModelPackageDetailResponse,
    OntologyModelPackageExportResponse,
    OntologyModelPackageListResponse,
    OntologyModelPackageSummaryResponse,
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
from semantic_lighthouse.services.ontology_draft_reviews import (
    DraftReviewError,
    review_modeling_drafts,
)

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
    project_id: str | None = Query(default=None),
    source_dataset_id: str | None = Query(default=None),
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
    if project_id:
        base = base.where(OntologyModelingDraft.project_id == project_id)
    if source_dataset_id:
        base = base.where(OntologyModelingDraft.source_dataset_id == source_dataset_id)
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

    # Validate project_id and source_dataset_id when present
    if body.source_dataset_id and not body.project_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="project_id is required when source_dataset_id is provided",
        )
    if body.project_id:
        proj = db.get(BusinessProject, body.project_id)
        if proj is None or proj.group_id != group_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="project_id not found in this group",
            )
    if body.source_dataset_id:
        ds = db.get(DatasetAsset, body.source_dataset_id)
        if ds is None or ds.group_id != group_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="source_dataset_id not found in this group",
            )
        if ds.project_id != body.project_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="source_dataset_id must belong to the specified project_id",
            )

    # At least one proper evidence pointer is required.
    # evidence_refs alone is NOT sufficient — it is supplemental metadata only.
    has_evidence = (
        body.source_entity_id
        or body.source_relation_id
        or body.source_issue_id
        or body.source_rag_run_id
        or body.source_dataset_id
    )
    if not has_evidence:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one source pointer (source_entity_id, source_relation_id, "
            "source_issue_id, source_rag_run_id, source_dataset_id) is required "
            "to create a draft. evidence_refs alone is not sufficient.",
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
        project_id=body.project_id,
        source_dataset_id=body.source_dataset_id,
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

    try:
        drafts, reviewed_at = review_modeling_drafts(
            db=db,
            group_id=group_id,
            draft_ids=body.draft_ids,
            decision=body.status,
            reviewer_id=current_user.id,
            review_note=body.review_note,
        )
    except DraftReviewError as exc:
        error_status = (
            status.HTTP_404_NOT_FOUND
            if exc.code == "draft_not_found"
            else status.HTTP_409_CONFLICT
        )
        raise HTTPException(status_code=error_status, detail=exc.message) from exc

    return OntologyModelingDraftBatchReviewResponse(
        reviewed_count=len(drafts),
        status=body.status,
        draft_ids=[d.id for d in drafts],
        reviewed_by=current_user.id,
        reviewed_at=reviewed_at,
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

    try:
        drafts, _ = review_modeling_drafts(
            db=db,
            group_id=group_id,
            draft_ids=[draft_id],
            decision=body.status,
            reviewer_id=current_user.id,
            review_note=body.review_note,
        )
    except DraftReviewError as exc:
        if exc.code == "draft_not_found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Draft not found",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Draft has already been reviewed",
        ) from exc

    draft = drafts[0]
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


# ── Phase 12.4: model package API ─────────────────────────────────────


@router.post(
    "/packages",
    response_model=OntologyModelPackageBuildResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_package(
    group_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Build an immutable model package from accepted drafts. Owner/admin only.

    Returns 201 with created=true on new package, 200 with created=false
    if identical content already exists. 409 on no-accepted/quality-errors/
    missing-dependency. Never modifies drafts.
    """
    require_group_role(db, current_user.id, group_id, {"owner", "admin"})

    from semantic_lighthouse.services.ontology_packages import (
        PackageBuildError,
        build_model_package,
    )

    try:
        pkg, created = build_model_package(db, group_id, current_user.id)
    except PackageBuildError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e.message)

    resp = OntologyModelPackageBuildResponse(
        id=pkg.id, version=pkg.version, content_hash=pkg.content_hash,
        draft_count=pkg.draft_count, quality_status=pkg.quality_status,
        created=created,
    )
    from fastapi.responses import JSONResponse
    return JSONResponse(
        content=resp.model_dump(), status_code=201 if created else 200,
    )


@router.get("/packages", response_model=OntologyModelPackageListResponse)
def list_packages(
    group_id: str,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OntologyModelPackageListResponse:
    """List legacy group-scoped packages. Any member can read."""
    get_membership_or_404(db, current_user.id, group_id)

    base = select(OntologyModelPackage).where(
        OntologyModelPackage.group_id == group_id,
        OntologyModelPackage.scope_key == "group",
    )
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.scalars(
        base.order_by(OntologyModelPackage.version.desc()).offset(offset).limit(limit)
    ).all()

    return OntologyModelPackageListResponse(
        packages=[_pkg_summary(p) for p in rows],
        total=total,
    )


@router.get(
    "/packages/{package_id}",
    response_model=OntologyModelPackageDetailResponse,
)
def get_package(
    group_id: str,
    package_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OntologyModelPackageDetailResponse:
    """Get full package detail including contract JSON. Any member can read."""
    get_membership_or_404(db, current_user.id, group_id)

    pkg = db.scalar(
        select(OntologyModelPackage).where(
            OntologyModelPackage.id == package_id,
            OntologyModelPackage.group_id == group_id,
        )
    )
    if pkg is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Package not found")
    return _pkg_detail(pkg)


@router.get(
    "/packages/{package_id}/export",
    response_model=OntologyModelPackageExportResponse,
)
def export_package(
    group_id: str,
    package_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OntologyModelPackageExportResponse:
    """Export package contract as stable JSON. Any member can read.

    This is a JSON contract export — not a production publish.
    """
    get_membership_or_404(db, current_user.id, group_id)

    pkg = db.scalar(
        select(OntologyModelPackage).where(
            OntologyModelPackage.id == package_id,
            OntologyModelPackage.group_id == group_id,
        )
    )
    if pkg is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Package not found")
    return OntologyModelPackageExportResponse(
        package_id=pkg.id,
        version=pkg.version,
        schema_version=pkg.schema_version,
        content_hash=pkg.content_hash,
        quality_status=pkg.quality_status,
        contract=pkg.contract_json,
    )


# ── Phase 13.4: business contract export ─────────────────────────────────


@router.get(
    "/packages/{package_id}/contract",
    response_model=BusinessContractManifestResponse,
)
def get_contract(
    group_id: str,
    package_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BusinessContractManifestResponse:
    """Export compiled business_v1 contract manifest. Any member can read.

    Returns the compiled business manifest with semantic_hash, provenance,
    and whitelisted business definitions. 422 if the package fails
    business_v1 validation (including contract_profile_mismatch).
    Read-only — never modifies packages, drafts, or database state.
    """
    get_membership_or_404(db, current_user.id, group_id)

    pkg = db.scalar(
        select(OntologyModelPackage).where(
            OntologyModelPackage.id == package_id,
            OntologyModelPackage.group_id == group_id,
        )
    )
    if pkg is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Package not found",
        )

    from semantic_lighthouse.services.business_contract_compiler import (
        BusinessContractCompilationError,
        compile_business_contract,
    )

    try:
        manifest = compile_business_contract(pkg)
    except BusinessContractCompilationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": str(e),
                "validation_result": e.validation_result,
            },
        )

    return BusinessContractManifestResponse(**manifest)


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
        project_id=d.project_id,
        source_dataset_id=d.source_dataset_id,
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


def _pkg_summary(p: OntologyModelPackage) -> OntologyModelPackageSummaryResponse:
    return OntologyModelPackageSummaryResponse(
        id=p.id, group_id=p.group_id, version=p.version,
        schema_version=p.schema_version, content_hash=p.content_hash,
        draft_count=p.draft_count, quality_status=p.quality_status,
        project_id=p.project_id,
        created_by=p.created_by, created_at=p.created_at,
    )


def _pkg_detail(p: OntologyModelPackage) -> OntologyModelPackageDetailResponse:
    return OntologyModelPackageDetailResponse(
        id=p.id, group_id=p.group_id, version=p.version,
        schema_version=p.schema_version, content_hash=p.content_hash,
        draft_count=p.draft_count, quality_status=p.quality_status,
        project_id=p.project_id,
        created_by=p.created_by, created_at=p.created_at,
        contract_json=p.contract_json,
        source_draft_ids=p.source_draft_ids,
        quality_summary=p.quality_summary,
    )


# ── Phase 14.3: Dataset-to-Model Bridge ───────────────────────────────────

project_model_router = APIRouter(
    prefix="/groups/{group_id}/projects/{project_id}/model-drafts",
    tags=["dataset-modeling"],
)


def _get_project_or_404(
    db: Session, project_id: str, group_id: str
) -> "BusinessProject":
    """Fetch project and enforce group_id match (404 on mismatch)."""
    project = db.get(BusinessProject, project_id)
    if project is None or project.group_id != group_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )
    return project


@project_model_router.post("/generate", response_model=DatasetModelingResponse)
def generate_dataset_model_drafts(
    group_id: str,
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DatasetModelingResponse:
    """Generate deterministic business_v1 modeling drafts from project dataset profiles.

    Owner/admin only. Idempotent — re-running produces no duplicates.
    Never modifies existing drafts. Does NOT generate action_type drafts.

    Stage: project must be at data/model/validate/pilot (not goal).
    First successful generation advances data → model.
    """
    require_group_role(db, current_user.id, group_id, {"owner", "admin"})

    project = db.get(BusinessProject, project_id)
    if project is None or project.group_id != group_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )

    if project.status == "archived":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot generate drafts for an archived project",
        )

    if project.stage == "goal":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Project must reach data stage before model drafts can be generated. "
            "Upload a dataset first.",
        )

    # Check for ready datasets
    ready_count = db.scalar(
        select(func.count()).select_from(
            select(DatasetAsset).where(
                DatasetAsset.project_id == project_id,
                DatasetAsset.group_id == group_id,
                DatasetAsset.status == "ready",
            ).subquery()
        )
    ) or 0

    if ready_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No ready datasets found in this project. Upload a dataset first.",
        )

    from semantic_lighthouse.services.dataset_modeling import generate_dataset_drafts
    from semantic_lighthouse.services.projects import advance_stage

    try:
        result = generate_dataset_drafts(db, group_id, project_id, current_user.id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e

    # Advance stage: data → model if we generated or already had drafts
    if project.stage == "data" and (result["generated_count"] > 0 or result["existing_count"] > 0):
        advance_stage("data", "model")
        project.stage = "model"
        db.commit()

    return DatasetModelingResponse(
        generated_count=result["generated_count"],
        existing_count=result["existing_count"],
        skipped_count=result["skipped_count"],
        counts_by_type=result["counts_by_type"],
        issues=result["issues"],
    )


# ── Phase 14.4: Project Validation Gate ───────────────────────────────────


@project_model_router.get("/quality", response_model=OntologyDraftQualityResponse)
def get_project_model_quality(
    group_id: str,
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OntologyDraftQualityResponse:
    """Get quality status of project-scoped drafts (member+)."""
    get_membership_or_404(db, current_user.id, group_id)
    _get_project_or_404(db, project_id, group_id)

    from semantic_lighthouse.services.ontology_draft_quality import (
        validate_modeling_drafts,
    )

    result = validate_modeling_drafts(db, group_id, project_id=project_id)
    return OntologyDraftQualityResponse(**result)


@project_model_router.post("/packages", response_model=OntologyModelPackageBuildResponse,
                           status_code=status.HTTP_201_CREATED)
def create_project_package(
    group_id: str,
    project_id: str,
    body: ProjectPackageBuildRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Build an immutable model package from project accepted drafts.

    Owner/admin only. WARN overrides require allow_warnings=true + non-empty
    override_reason. FAIL always blocks. Idempotent by content hash.
    """
    require_group_role(db, current_user.id, group_id, {"owner", "admin"})
    project = _get_project_or_404(db, project_id, group_id)

    if project.status == "archived":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot build packages for an archived project",
        )
    if project.stage == "goal":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Project must reach model stage before building packages",
        )

    allow_warnings = body.allow_warnings if body else False
    override_reason = (body.override_reason or "").strip() if body else ""

    # Check for proposed drafts (must all be reviewed)
    proposed_count = db.scalar(
        select(func.count()).select_from(
            select(OntologyModelingDraft).where(
                OntologyModelingDraft.project_id == project_id,
                OntologyModelingDraft.group_id == group_id,
                OntologyModelingDraft.status == "proposed",
            ).subquery()
        )
    ) or 0

    if proposed_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{proposed_count} draft(s) still in proposed status. "
            "All drafts must be accepted or rejected before building a package.",
        )

    from semantic_lighthouse.services.ontology_draft_quality import (
        validate_modeling_drafts,
    )
    from semantic_lighthouse.services.ontology_packages import (
        PackageBuildError,
        build_model_package,
    )
    from semantic_lighthouse.services.projects import advance_stage

    quality = validate_modeling_drafts(db, group_id, project_id=project_id)

    if quality["status"] == "FAIL":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Quality FAIL: {quality['error_count']} error(s). "
            "FAIL status cannot be overridden.",
        )

    if quality["status"] == "WARN":
        if not allow_warnings:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Quality WARN: {quality['warning_count']} warning(s). "
                "Set allow_warnings=true and provide override_reason to proceed.",
            )
        if not override_reason:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="override_reason is required when allow_warnings=true",
            )

    # Build WARN override audit to be written in same transaction as package
    override_audit = None
    if quality["status"] == "WARN" and allow_warnings:
        override_audit = {
            "warning_override": True,
            "override_reason": override_reason,
            "overridden_by": current_user.id,
            "overridden_at": utc_now().isoformat(),
        }

    try:
        pkg, created = build_model_package(
            db, group_id, current_user.id, project_id=project_id,
            quality_summary_override=override_audit,
        )
    except PackageBuildError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e.message)

    # Advance stage model → validate (same transaction as package creation)
    if created and project.stage == "model":
        advance_stage("model", "validate")
        project.stage = "validate"
        db.commit()

    return OntologyModelPackageBuildResponse(
        id=pkg.id, version=pkg.version, content_hash=pkg.content_hash,
        draft_count=pkg.draft_count, quality_status=pkg.quality_status,
        project_id=pkg.project_id, created=created,
    )


@project_model_router.get("/packages", response_model=OntologyModelPackageListResponse)
def list_project_packages(
    group_id: str,
    project_id: str,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OntologyModelPackageListResponse:
    """List project-scoped packages (member+)."""
    get_membership_or_404(db, current_user.id, group_id)
    _get_project_or_404(db, project_id, group_id)

    scope_key = f"project:{project_id}"
    base = select(OntologyModelPackage).where(
        OntologyModelPackage.group_id == group_id,
        OntologyModelPackage.scope_key == scope_key,
    )
    total = db.scalar(select(func.count()).select_from(base.subquery()))
    pkgs = db.scalars(
        base.order_by(OntologyModelPackage.version.desc()).offset(offset).limit(limit)
    ).all()
    return OntologyModelPackageListResponse(
        packages=[_pkg_summary(p) for p in pkgs],
        total=total or 0,
    )


@project_model_router.get("/packages/{package_id}",
                          response_model=OntologyModelPackageDetailResponse)
def get_project_package(
    package_id: str,
    group_id: str,
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OntologyModelPackageDetailResponse:
    """Get a project-scoped package detail (member+)."""
    get_membership_or_404(db, current_user.id, group_id)
    _get_project_or_404(db, project_id, group_id)

    pkg = db.get(OntologyModelPackage, package_id)
    if pkg is None or pkg.group_id != group_id or pkg.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Package not found"
        )
    return _pkg_detail(pkg)


@project_model_router.get("/packages/{package_id}/contract",
                          response_model=BusinessContractManifestResponse)
def get_project_contract(
    package_id: str,
    group_id: str,
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BusinessContractManifestResponse:
    """Export a compiled business contract from a project package (member+)."""
    get_membership_or_404(db, current_user.id, group_id)
    _get_project_or_404(db, project_id, group_id)

    pkg = db.get(OntologyModelPackage, package_id)
    if pkg is None or pkg.group_id != group_id or pkg.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Package not found"
        )

    from semantic_lighthouse.services.business_contract_compiler import (
        BusinessContractCompilationError,
        compile_business_contract,
    )

    try:
        compiled = compile_business_contract(pkg)
    except BusinessContractCompilationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        ) from e

    return BusinessContractManifestResponse(**compiled)
