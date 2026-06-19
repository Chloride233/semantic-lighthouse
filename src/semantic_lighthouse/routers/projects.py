"""Phase 14.1 — business pilot project API.

Each group can contain multiple pilot projects.
Stage is backend-controlled; clients cannot set it arbitrarily.
Permissions: member read, owner/admin write/archive.
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
from semantic_lighthouse.models import BusinessProject, User, utc_now
from semantic_lighthouse.schemas import (
    BusinessProjectCreateRequest,
    BusinessProjectListResponse,
    BusinessProjectResponse,
    BusinessProjectUpdateRequest,
)

router = APIRouter(prefix="/groups/{group_id}/projects", tags=["projects"])


def _project_response(project: BusinessProject) -> BusinessProjectResponse:
    return BusinessProjectResponse(
        id=project.id,
        group_id=project.group_id,
        name=project.name,
        business_goal=project.business_goal,
        entry_mode=project.entry_mode,
        industry_template=project.industry_template,
        stage=project.stage,
        status=project.status,
        created_by=project.created_by,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


@router.post("", status_code=status.HTTP_201_CREATED, response_model=BusinessProjectResponse)
def create_project(
    body: BusinessProjectCreateRequest,
    group_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BusinessProjectResponse:
    """Create a new business pilot project (owner/admin only)."""
    require_group_role(db, current_user.id, group_id, {"owner", "admin"})

    project = BusinessProject(
        group_id=group_id,
        name=body.name,
        business_goal=body.business_goal,
        entry_mode=body.entry_mode,
        industry_template=body.industry_template,
        stage="goal",
        status="active",
        created_by=current_user.id,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return _project_response(project)


@router.get("", response_model=BusinessProjectListResponse)
def list_projects(
    group_id: str,
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BusinessProjectListResponse:
    """List group-scoped projects with optional status filter."""
    get_membership_or_404(db, current_user.id, group_id)

    base = select(BusinessProject).where(BusinessProject.group_id == group_id)
    if status_filter:
        base = base.where(BusinessProject.status == status_filter)

    total = db.scalar(select(func.count()).select_from(base.subquery()))
    projects = db.scalars(
        base.order_by(BusinessProject.created_at.desc()).offset(offset).limit(limit)
    ).all()

    return BusinessProjectListResponse(
        projects=[_project_response(p) for p in projects],
        total=total or 0,
    )


@router.get("/{project_id}", response_model=BusinessProjectResponse)
def get_project(
    project_id: str,
    group_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BusinessProjectResponse:
    """Get a single project detail (member+)."""
    get_membership_or_404(db, current_user.id, group_id)

    project = db.get(BusinessProject, project_id)
    if project is None or project.group_id != group_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )
    return _project_response(project)


@router.patch("/{project_id}", response_model=BusinessProjectResponse)
def update_project(
    project_id: str,
    body: BusinessProjectUpdateRequest,
    group_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BusinessProjectResponse:
    """Update project metadata (owner/admin only).

    Only name, business_goal, entry_mode, and industry_template
    are editable. Stage and status cannot be changed via PATCH.
    """
    require_group_role(db, current_user.id, group_id, {"owner", "admin"})

    project = db.get(BusinessProject, project_id)
    if project is None or project.group_id != group_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )

    # model_dump(exclude_unset=True) distinguishes "not provided"
    # from "explicitly set to None" — important for clearing
    # optional fields like industry_template.
    update_fields = body.model_dump(exclude_unset=True)
    if "name" in update_fields:
        project.name = update_fields["name"]
    if "business_goal" in update_fields:
        project.business_goal = update_fields["business_goal"]
    if "entry_mode" in update_fields:
        project.entry_mode = update_fields["entry_mode"]
    if "industry_template" in update_fields:
        project.industry_template = update_fields["industry_template"]

    db.commit()
    db.refresh(project)
    return _project_response(project)


@router.post("/{project_id}/archive", response_model=BusinessProjectResponse)
def archive_project(
    project_id: str,
    group_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BusinessProjectResponse:
    """Archive a project (owner/admin only). Idempotent."""
    require_group_role(db, current_user.id, group_id, {"owner", "admin"})

    project = db.get(BusinessProject, project_id)
    if project is None or project.group_id != group_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )

    project.status = "archived"
    project.updated_at = utc_now()
    db.commit()
    db.refresh(project)
    return _project_response(project)
