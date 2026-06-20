"""S2.2 — Project Evidence Links router.

Explicit user-created links between a Pilot project and group-scoped evidence
(Document or RagRun). Owner/admin write; member read. Group+project dual isolation.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select, and_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from semantic_lighthouse.database import get_db
from semantic_lighthouse.dependencies import get_current_user, get_membership_or_404, require_group_role
from semantic_lighthouse.models import (
    BusinessProject,
    Document,
    OntologyRuntimeAudit,
    ProjectEvidenceLink,
    RagRun,
    User,
    new_id,
    utc_now,
)
from semantic_lighthouse.schemas import (
    EVIDENCE_ROLES,
    EVIDENCE_TYPES,
    EvidenceLinkCreateRequest,
    EvidenceLinkListResponse,
    EvidenceLinkResponse,
    EvidenceProvenance,
)

router = APIRouter(
    prefix="/groups/{group_id}/projects/{project_id}/evidence-links",
    tags=["evidence-links"],
)


def _get_project_or_404(db: Session, project_id: str, group_id: str) -> BusinessProject:
    project = db.get(BusinessProject, project_id)
    if project is None or project.group_id != group_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


def _build_provenance(db: Session, evidence_type: str, evidence_id: str) -> EvidenceProvenance | None:
    """Build minimal provenance. Never exposes paths, content, or secrets."""
    prov = EvidenceProvenance()
    if evidence_type == "document":
        doc = db.get(Document, evidence_id)
        if doc is None:
            prov.unavailable = True
            prov.evidence_status = "gone"
            return prov
        prov.evidence_title = doc.title
        prov.evidence_status = doc.status
        prov.file_name = doc.file_name
        fm = doc.frontmatter
        prov.source_label = fm.get("source") or doc.title if isinstance(fm, dict) else doc.title
        if doc.created_at:
            prov.evidence_created_at = doc.created_at.isoformat()
    elif evidence_type == "rag_run":
        run = db.get(RagRun, evidence_id)
        if run is None:
            prov.unavailable = True
            prov.evidence_status = "gone"
            return prov
        prov.evidence_status = run.status
        prov.question = (run.question or "")[:120]
        prov.confidence = run.confidence
        prov.retrieval_method = run.retrieval_method
        prov.citation_count = len(run.citations) if isinstance(run.citations, list) else None
        if run.created_at:
            prov.evidence_created_at = run.created_at.isoformat()
    return prov


def _validate_evidence(
    db: Session, evidence_type: str, evidence_id: str, group_id: str,
) -> None:
    """Validate evidence exists, belongs to group, and has linkable status."""
    if evidence_type not in EVIDENCE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid evidence_type"
        )
    if evidence_type == "document":
        evidence = db.get(Document, evidence_id)
        if evidence is None or evidence.group_id != group_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Evidence not found"
            )
        if evidence.status != "ready":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Only ready documents can be linked as project evidence",
            )
    else:  # rag_run
        evidence = db.get(RagRun, evidence_id)
        if evidence is None or evidence.group_id != group_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Evidence not found"
            )
        if evidence.status != "success":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Only successful RAG runs can be linked as project evidence",
            )


def _write_audit(
    db: Session, user: User, group_id: str, project_id: str,
    operation: str, object_type: str,
) -> None:
    """Write OntologyRuntimeAudit. field_names stores only field name strings."""
    db.add(OntologyRuntimeAudit(
        user_id=user.id,
        group_id=group_id,
        project_id=project_id,
        operation=operation,
        object_type=object_type,
        field_names=["evidence_type", "role", "note", "status"],
        outcome="success",
    ))


def _link_response(
    link: ProjectEvidenceLink, provenance: EvidenceProvenance | None,
) -> EvidenceLinkResponse:
    return EvidenceLinkResponse(
        id=link.id,
        project_id=link.project_id,
        evidence_type=link.evidence_type,
        evidence_id=link.evidence_id,
        role=link.role,
        note=link.note,
        status=link.status,
        created_by=link.created_by,
        created_at=link.created_at.isoformat() if link.created_at else "",
        updated_at=link.updated_at.isoformat() if link.updated_at else "",
        removed_by=link.removed_by,
        removed_at=link.removed_at.isoformat() if link.removed_at else None,
        provenance=provenance,
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  Endpoints
# ═══════════════════════════════════════════════════════════════════════════════


@router.post("", response_model=EvidenceLinkResponse, status_code=201)
def create_evidence_link(
    group_id: str,
    project_id: str,
    body: EvidenceLinkCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Create a project evidence link. Owner/admin only."""
    require_group_role(db, user.id, group_id, {"owner", "admin"})
    project = _get_project_or_404(db, project_id, group_id)

    if body.role not in EVIDENCE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid role"
        )
    if project.status == "archived":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot link evidence to an archived project",
        )

    _validate_evidence(db, body.evidence_type, body.evidence_id, group_id)
    note = body.note.strip() if body.note else None

    existing = db.execute(
        select(ProjectEvidenceLink).where(
            ProjectEvidenceLink.project_id == project_id,
            ProjectEvidenceLink.evidence_type == body.evidence_type,
            ProjectEvidenceLink.evidence_id == body.evidence_id,
        )
    ).scalar_one_or_none()

    # Active duplicate — idempotent, no audit
    if existing is not None and existing.status == "active":
        prov = _build_provenance(db, existing.evidence_type, existing.evidence_id)
        return _link_response(existing, prov)

    # Removed link — reactivate
    if existing is not None and existing.status == "removed":
        existing.status = "active"
        existing.role = body.role
        existing.note = note
        existing.removed_by = None
        existing.removed_at = None
        existing.updated_at = utc_now()
        _write_audit(db, user, group_id, project_id, "evidence_relink", body.evidence_type)
        db.commit()
        db.refresh(existing)
        prov = _build_provenance(db, existing.evidence_type, existing.evidence_id)
        return _link_response(existing, prov)

    # New link
    try:
        link = ProjectEvidenceLink(
            id=new_id(),
            group_id=group_id,
            project_id=project_id,
            evidence_type=body.evidence_type,
            evidence_id=body.evidence_id,
            role=body.role,
            note=note,
            status="active",
            created_by=user.id,
        )
        db.add(link)
        db.flush()
        _write_audit(db, user, group_id, project_id, "evidence_link", body.evidence_type)
        db.commit()
        db.refresh(link)
        prov = _build_provenance(db, link.evidence_type, link.evidence_id)
        return _link_response(link, prov)
    except IntegrityError:
        db.rollback()
        existing_race = db.execute(
            select(ProjectEvidenceLink).where(
                ProjectEvidenceLink.project_id == project_id,
                ProjectEvidenceLink.evidence_type == body.evidence_type,
                ProjectEvidenceLink.evidence_id == body.evidence_id,
            )
        ).scalar_one_or_none()
        if existing_race is not None:
            if existing_race.status == "active":
                prov = _build_provenance(db, existing_race.evidence_type, existing_race.evidence_id)
                return _link_response(existing_race, prov)
            if existing_race.status == "removed":
                existing_race.status = "active"
                existing_race.role = body.role
                existing_race.note = note
                existing_race.removed_by = None
                existing_race.removed_at = None
                existing_race.updated_at = utc_now()
                _write_audit(db, user, group_id, project_id, "evidence_relink", body.evidence_type)
                db.commit()
                db.refresh(existing_race)
                prov = _build_provenance(db, existing_race.evidence_type, existing_race.evidence_id)
                return _link_response(existing_race, prov)
        raise


@router.get("", response_model=EvidenceLinkListResponse)
def list_evidence_links(
    group_id: str,
    project_id: str,
    status_filter: str = "active",
    evidence_type: str | None = None,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List project evidence links. Member+."""
    get_membership_or_404(db, user.id, group_id)
    _get_project_or_404(db, project_id, group_id)

    conditions = [ProjectEvidenceLink.project_id == project_id]
    if status_filter == "active":
        conditions.append(ProjectEvidenceLink.status == "active")
    elif status_filter == "removed":
        conditions.append(ProjectEvidenceLink.status == "removed")

    if evidence_type and evidence_type in EVIDENCE_TYPES:
        conditions.append(ProjectEvidenceLink.evidence_type == evidence_type)

    total = db.scalar(
        select(func.count()).select_from(ProjectEvidenceLink).where(and_(*conditions))
    ) or 0

    links = db.scalars(
        select(ProjectEvidenceLink)
        .where(and_(*conditions))
        .order_by(ProjectEvidenceLink.created_at.desc())
        .offset(offset)
        .limit(limit)
    ).all()

    items = [
        _link_response(link, _build_provenance(db, link.evidence_type, link.evidence_id))
        for link in links
    ]
    return EvidenceLinkListResponse(links=items, total=total, limit=limit, offset=offset)


@router.delete("/{link_id}", response_model=EvidenceLinkResponse)
def remove_evidence_link(
    group_id: str,
    project_id: str,
    link_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Remove a project evidence link (soft-delete). Owner/admin only."""
    require_group_role(db, user.id, group_id, {"owner", "admin"})
    _get_project_or_404(db, project_id, group_id)

    link = db.get(ProjectEvidenceLink, link_id)
    if link is None or link.group_id != group_id or link.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Evidence link not found"
        )

    if link.status == "removed":
        prov = _build_provenance(db, link.evidence_type, link.evidence_id)
        return _link_response(link, prov)

    link.status = "removed"
    link.removed_by = user.id
    link.removed_at = utc_now()
    _write_audit(db, user, group_id, project_id, "evidence_unlink", link.evidence_type)
    db.commit()
    db.refresh(link)
    prov = _build_provenance(db, link.evidence_type, link.evidence_id)
    return _link_response(link, prov)
