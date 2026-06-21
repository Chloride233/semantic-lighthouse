"""Phase 16.1 — Pilot Outcome Record API.

Immutable FDE delivery snapshots for business pilot projects.
Owner/admin create; member+ read/list. No PATCH/DELETE in v1.
Never stores raw prompts, answers, secrets, or paths.
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
    OntologyModelPackage,
    PilotOutcomeRecord,
    ProjectEvidenceLink,
    User,
)
from semantic_lighthouse.routers.evidence_links import _build_provenance
from semantic_lighthouse.schemas import (
    PilotOutcomeCreateRequest,
    PilotOutcomeListResponse,
    PilotOutcomeResponse,
)

router = APIRouter(
    prefix="/groups/{group_id}/projects/{project_id}/outcomes",
    tags=["outcomes"],
)


def _get_project_or_404(db: Session, project_id: str, group_id: str) -> BusinessProject:
    project = db.get(BusinessProject, project_id)
    if project is None or project.group_id != group_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )
    return project


def _build_evidence_refs(
    db: Session, group_id: str, project_id: str, link_ids: list[str],
) -> list[dict]:
    """Build bounded evidence refs from active project evidence links.

    Validates each link: must exist, be active, same group, same project.
    Never stores raw_content, raw_answer, source_path, storage_path, or secrets.
    """
    refs: list[dict] = []
    for link_id in link_ids:
        link = db.get(ProjectEvidenceLink, link_id)
        if link is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Evidence link {link_id} not found",
            )
        if link.group_id != group_id or link.project_id != project_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Evidence link {link_id} does not belong to this project",
            )
        if link.status != "active":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Evidence link {link_id} is not active (status={link.status})",
            )
        provenance = _build_provenance(db, link.evidence_type, link.evidence_id)
        refs.append({
            "link_id": link.id,
            "evidence_type": link.evidence_type,
            "role": link.role,
            "provenance": provenance.model_dump(exclude_none=True) if provenance else {},
        })
    return refs


def _build_package_refs(
    db: Session, group_id: str, project_id: str, package_ids: list[str],
) -> list[dict]:
    """Build bounded package refs.

    Validates each package: must exist, same group, same project if scoped.
    Stores only id, version, content_hash, quality_status, draft_count.
    Never stores contract_json, source_draft_ids, or quality_summary details.
    """
    refs: list[dict] = []
    for pkg_id in package_ids:
        pkg = db.get(OntologyModelPackage, pkg_id)
        if pkg is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Package {pkg_id} not found",
            )
        if pkg.group_id != group_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Package {pkg_id} does not belong to this group",
            )
        # If the package is project-scoped, it must match the project
        if pkg.project_id is not None and pkg.project_id != project_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Package {pkg_id} is scoped to a different project",
            )
        refs.append({
            "package_id": pkg.id,
            "version": pkg.version,
            "content_hash": pkg.content_hash,
            "quality_status": pkg.quality_status,
            "draft_count": pkg.draft_count,
        })
    return refs


def _outcome_response(record: PilotOutcomeRecord) -> PilotOutcomeResponse:
    return PilotOutcomeResponse(
        id=record.id,
        group_id=record.group_id,
        project_id=record.project_id,
        title=record.title,
        business_goal_snapshot=record.business_goal_snapshot,
        selected_evidence_refs=record.selected_evidence_refs,
        package_refs=record.package_refs,
        query_refs=record.query_refs,
        decision_summary=record.decision_summary,
        risks=record.risks,
        next_actions=record.next_actions,
        created_by=record.created_by,
        created_at=record.created_at,
    )


@router.post("", status_code=status.HTTP_201_CREATED, response_model=PilotOutcomeResponse)
def create_outcome(
    group_id: str,
    project_id: str,
    body: PilotOutcomeCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PilotOutcomeResponse:
    """Create an immutable pilot outcome record (owner/admin only).

    Snapshots the project's current business_goal and builds bounded
    evidence/package refs from validated IDs. query_refs are validated
    for forbidden keys by the schema. Never stores raw data or secrets.
    """
    require_group_role(db, user.id, group_id, {"owner", "admin"})
    project = _get_project_or_404(db, project_id, group_id)

    # Build bounded evidence refs from validated link IDs
    evidence_refs = _build_evidence_refs(
        db, group_id, project_id, body.selected_evidence_link_ids,
    )

    # Build bounded package refs from validated package IDs
    package_refs = _build_package_refs(
        db, group_id, project_id, body.package_ids,
    )

    # query_refs already validated for forbidden keys by schema validator

    record = PilotOutcomeRecord(
        group_id=group_id,
        project_id=project_id,
        title=body.title,
        business_goal_snapshot=project.business_goal,
        selected_evidence_refs=evidence_refs,
        package_refs=package_refs,
        query_refs=body.query_refs,
        decision_summary=body.decision_summary,
        risks=body.risks,
        next_actions=body.next_actions,
        created_by=user.id,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return _outcome_response(record)


@router.get("", response_model=PilotOutcomeListResponse)
def list_outcomes(
    group_id: str,
    project_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PilotOutcomeListResponse:
    """List outcome records for a project (member+). Latest first."""
    get_membership_or_404(db, user.id, group_id)
    _get_project_or_404(db, project_id, group_id)

    base = select(PilotOutcomeRecord).where(
        PilotOutcomeRecord.group_id == group_id,
        PilotOutcomeRecord.project_id == project_id,
    )
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0

    records = db.scalars(
        base.order_by(PilotOutcomeRecord.created_at.desc())
        .offset(offset)
        .limit(limit)
    ).all()

    return PilotOutcomeListResponse(
        outcomes=[_outcome_response(r) for r in records],
        total=total,
    )


@router.get("/{outcome_id}", response_model=PilotOutcomeResponse)
def get_outcome(
    group_id: str,
    project_id: str,
    outcome_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PilotOutcomeResponse:
    """Get a single outcome record (member+). 404 across group/project boundary."""
    get_membership_or_404(db, user.id, group_id)
    _get_project_or_404(db, project_id, group_id)

    record = db.get(PilotOutcomeRecord, outcome_id)
    if (
        record is None
        or record.group_id != group_id
        or record.project_id != project_id
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Outcome record not found"
        )
    return _outcome_response(record)
