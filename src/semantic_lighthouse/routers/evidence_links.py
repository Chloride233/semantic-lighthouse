"""S2.2 — Project Evidence Links router.

Explicit user-created links between a Pilot project and group-scoped evidence
(Document or RagRun). Owner/admin write; member read. Group+project dual isolation.
"""

import re
from fastapi import APIRouter, Depends, HTTPException, Response, status
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

ALLOWED_STATUS_FILTERS = {"active", "removed", "all"}

# Patterns that indicate a suspicious path-like value in source_label
_UNSAFE_LABEL_RE = re.compile(r'[/\\]')  # rejects any path separators
_WIN_DRIVE_RE = re.compile(r'^[A-Za-z]:')  # rejects Windows drive letters


def _get_project_or_404(db: Session, project_id: str, group_id: str) -> BusinessProject:
    project = db.get(BusinessProject, project_id)
    if project is None or project.group_id != group_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


def _safe_source_label(doc: Document) -> str | None:
    """Return a safe display label, never a path or complex object."""
    fm = doc.frontmatter
    if isinstance(fm, dict):
        raw = fm.get("source")
        if isinstance(raw, str) and raw.strip():
            stripped = raw.strip()
            # Reject POSIX absolute paths
            if stripped.startswith("/"):
                return doc.title
            # Reject Windows drive paths and UNC
            if _WIN_DRIVE_RE.match(stripped):
                return doc.title
            if stripped.startswith("\\\\"):
                return doc.title
            # Reject anything containing path separators (relative paths, etc.)
            if _UNSAFE_LABEL_RE.search(stripped):
                return doc.title
            # Reject excessively long strings
            if len(stripped) > 200:
                return doc.title
            return stripped
    return doc.title


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
        prov.source_label = _safe_source_label(doc)
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


def _validate_evidence_status(
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


def _query_existing_link(db: Session, group_id: str, project_id: str,
                         evidence_type: str, evidence_id: str) -> ProjectEvidenceLink | None:
    """Query existing link with dual group_id + project_id isolation."""
    return db.execute(
        select(ProjectEvidenceLink).where(
            ProjectEvidenceLink.group_id == group_id,
            ProjectEvidenceLink.project_id == project_id,
            ProjectEvidenceLink.evidence_type == evidence_type,
            ProjectEvidenceLink.evidence_id == evidence_id,
        )
    ).scalar_one_or_none()


# ═══════════════════════════════════════════════════════════════════════════════
#  Endpoints
# ═══════════════════════════════════════════════════════════════════════════════


@router.post("", response_model=EvidenceLinkResponse)
def create_evidence_link(
    group_id: str,
    project_id: str,
    body: EvidenceLinkCreateRequest,
    response: Response,
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

    note = body.note.strip() if body.note else None
    if note == "":
        note = None

    # ── Step 1: Check existing link FIRST (dual-isolated query) ──
    existing = _query_existing_link(db, group_id, project_id, body.evidence_type, body.evidence_id)

    # Active duplicate — idempotent, no status checks, no audit, 200.
    # Returns existing record even if project or evidence is now archived.
    if existing is not None and existing.status == "active":
        response.status_code = 200
        prov = _build_provenance(db, existing.evidence_type, existing.evidence_id)
        return _link_response(existing, prov)

    # Removed link — reactivate, 200 (only if still valid)
    if existing is not None and existing.status == "removed":
        if project.status == "archived":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot relink evidence to an archived project",
            )
        _validate_evidence_status(db, body.evidence_type, body.evidence_id, group_id)
        existing.status = "active"
        existing.role = body.role
        existing.note = note
        existing.removed_by = None
        existing.removed_at = None
        existing.updated_at = utc_now()
        _write_audit(db, user, group_id, project_id, "evidence_relink", body.evidence_type)
        db.commit()
        db.refresh(existing)
        response.status_code = 200
        prov = _build_provenance(db, existing.evidence_type, existing.evidence_id)
        return _link_response(existing, prov)

    # ── Step 2: Only new links need project/evidence status checks ──
    if project.status == "archived":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot link evidence to an archived project",
        )

    _validate_evidence_status(db, body.evidence_type, body.evidence_id, group_id)

    # ── Step 3: Create new link, 201 ──
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
        response.status_code = 201
        prov = _build_provenance(db, link.evidence_type, link.evidence_id)
        return _link_response(link, prov)
    except IntegrityError:
        db.rollback()
        existing_race = _query_existing_link(
            db, group_id, project_id, body.evidence_type, body.evidence_id
        )
        if existing_race is not None:
            if existing_race.status == "active":
                response.status_code = 200
                prov = _build_provenance(db, existing_race.evidence_type, existing_race.evidence_id)
                return _link_response(existing_race, prov)
            if existing_race.status == "removed":
                if project.status == "archived":
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Cannot relink evidence to an archived project",
                    )
                existing_race.status = "active"
                existing_race.role = body.role
                existing_race.note = note
                existing_race.removed_by = None
                existing_race.removed_at = None
                existing_race.updated_at = utc_now()
                _write_audit(db, user, group_id, project_id, "evidence_relink", body.evidence_type)
                db.commit()
                db.refresh(existing_race)
                response.status_code = 200
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

    if status_filter not in ALLOWED_STATUS_FILTERS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="status_filter must be active, removed, or all",
        )
    if evidence_type is not None and evidence_type not in EVIDENCE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"evidence_type must be one of: {', '.join(sorted(EVIDENCE_TYPES))}",
        )
    if limit < 1 or limit > 100:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="limit must be between 1 and 100",
        )
    if offset < 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="offset must be >= 0",
        )

    conditions = [
        ProjectEvidenceLink.group_id == group_id,
        ProjectEvidenceLink.project_id == project_id,
    ]
    if status_filter == "active":
        conditions.append(ProjectEvidenceLink.status == "active")
    elif status_filter == "removed":
        conditions.append(ProjectEvidenceLink.status == "removed")

    if evidence_type:
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
    link.updated_at = utc_now()
    _write_audit(db, user, group_id, project_id, "evidence_unlink", link.evidence_type)
    db.commit()
    db.refresh(link)
    prov = _build_provenance(db, link.evidence_type, link.evidence_id)
    return _link_response(link, prov)
