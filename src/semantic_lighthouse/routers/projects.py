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
from semantic_lighthouse.models import (
    AgentRun,
    BusinessProject,
    Conversation,
    OntologyModelPackage,
    OntologyRuntimeAudit,
    PilotOutcomeRecord,
    ProjectEvidenceLink,
    Task,
    User,
    utc_now,
)
from semantic_lighthouse.routers.evidence_links import _build_provenance
from semantic_lighthouse.schemas import (
    BusinessProjectCreateRequest,
    BusinessProjectListResponse,
    BusinessProjectResponse,
    BusinessProjectUpdateRequest,
    OutcomeEvidenceCounts,
    OutcomeLatestInfo,
    OutcomePackageInfo,
    OutcomePackageSummary,
    OutcomeRuntimeSummary,
    PilotOutcomeSummaryResponse,
    ProjectSummaryResponse,
    TaskCountsByStatus,
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


# ── S2.4B Project Summary ──────────────────────────────────────────────────


def _summary_evidence(link: ProjectEvidenceLink, db: Session) -> dict:
    """Return link metadata plus the same safe provenance used by evidence links."""
    provenance = _build_provenance(db, link.evidence_type, link.evidence_id)
    return {
        "id": link.id,
        "evidence_type": link.evidence_type,
        "evidence_id": link.evidence_id,
        "role": link.role,
        "status": link.status,
        "created_at": link.created_at.isoformat() if link.created_at else "",
        "provenance": provenance.model_dump(exclude_none=True) if provenance else {},
    }


@router.get("/{project_id}/summary", response_model=ProjectSummaryResponse)
def get_project_summary(
    group_id: str,
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectSummaryResponse:
    """Read-only project summary. Member+."""
    get_membership_or_404(db, current_user.id, group_id)

    project = db.get(BusinessProject, project_id)
    if project is None or project.group_id != group_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    # Evidence
    evidence_links = db.scalars(
        select(ProjectEvidenceLink).where(
            ProjectEvidenceLink.group_id == group_id,
            ProjectEvidenceLink.project_id == project_id,
            ProjectEvidenceLink.status == "active",
        ).order_by(ProjectEvidenceLink.created_at.desc()).limit(5)
    ).all()
    evidence_count = db.scalar(
        select(func.count()).select_from(ProjectEvidenceLink).where(
            ProjectEvidenceLink.group_id == group_id,
            ProjectEvidenceLink.project_id == project_id,
            ProjectEvidenceLink.status == "active",
        )
    ) or 0

    # Conversations
    conversation_count = db.scalar(
        select(func.count()).select_from(Conversation).where(
            Conversation.group_id == group_id,
            Conversation.project_id == project_id,
        )
    ) or 0

    # Tasks by status
    task_statuses = db.execute(
        select(Task.status, func.count()).where(
            Task.group_id == group_id,
            Task.project_id == project_id,
        ).group_by(Task.status)
    ).all()
    task_counts = {"pending": 0, "in_progress": 0, "done": 0, "cancelled": 0}
    for status_val, count in task_statuses:
        if status_val in task_counts:
            task_counts[status_val] = count

    # Agent runs
    agent_run_count = db.scalar(
        select(func.count()).select_from(AgentRun).where(
            AgentRun.group_id == group_id,
            AgentRun.project_id == project_id,
        )
    ) or 0

    return ProjectSummaryResponse(
        project={
            "id": project.id,
            "name": project.name,
            "business_goal": project.business_goal,
            "stage": project.stage,
            "status": project.status,
        },
        evidence_count=evidence_count,
        recent_evidence=[_summary_evidence(link, db) for link in evidence_links],
        conversation_count=conversation_count,
        task_count=TaskCountsByStatus(**task_counts),
        agent_run_count=agent_run_count,
    )


# ── Phase 16.2: Pilot Outcome Summary ───────────────────────────────────────


@router.get(
    "/{project_id}/outcome-summary",
    response_model=PilotOutcomeSummaryResponse,
)
def get_outcome_summary(
    group_id: str,
    project_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PilotOutcomeSummaryResponse:
    """Read-only FDE delivery summary (member+).

    Aggregates project metadata, latest PilotOutcomeRecord, active evidence
    counts by type/role, package summary, and minimal runtime operation counts.
    Never exposes raw prompts, answers, paths, secrets, or stack traces.
    Does not create, update, or delete any records.
    """
    get_membership_or_404(db, user.id, group_id)

    project = db.get(BusinessProject, project_id)
    if project is None or project.group_id != group_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )

    # ── Latest outcome record ──────────────────────────────────────────
    latest = db.scalars(
        select(PilotOutcomeRecord)
        .where(
            PilotOutcomeRecord.group_id == group_id,
            PilotOutcomeRecord.project_id == project_id,
        )
        .order_by(PilotOutcomeRecord.created_at.desc(), PilotOutcomeRecord.id.desc())
        .limit(1)
    ).first()

    latest_outcome = None
    decision_summary = ""
    risks: list[str] = []
    next_actions: list[str] = []
    if latest is not None:
        latest_outcome = OutcomeLatestInfo(
            id=latest.id,
            title=latest.title,
            created_at=latest.created_at,
            decision_summary=latest.decision_summary,
            risks=latest.risks if isinstance(latest.risks, list) else [],
            next_actions=latest.next_actions if isinstance(latest.next_actions, list) else [],
        )
        decision_summary = latest.decision_summary
        risks = latest.risks if isinstance(latest.risks, list) else []
        next_actions = latest.next_actions if isinstance(latest.next_actions, list) else []

    # ── Evidence summary (active links only, bounded counts) ────────────
    active_links = db.scalars(
        select(ProjectEvidenceLink).where(
            ProjectEvidenceLink.group_id == group_id,
            ProjectEvidenceLink.project_id == project_id,
            ProjectEvidenceLink.status == "active",
        )
    ).all()

    by_type: dict[str, int] = {}
    by_role: dict[str, int] = {}
    for link in active_links:
        by_type[link.evidence_type] = by_type.get(link.evidence_type, 0) + 1
        by_role[link.role] = by_role.get(link.role, 0) + 1

    evidence_summary = OutcomeEvidenceCounts(
        total_active=len(active_links),
        by_type=by_type,
        by_role=by_role,
    )

    # ── Package summary (project-scoped packages) ───────────────────────
    packages = db.scalars(
        select(OntologyModelPackage)
        .where(
            OntologyModelPackage.group_id == group_id,
            OntologyModelPackage.project_id == project_id,
        )
        .order_by(OntologyModelPackage.created_at.desc())
    ).all()

    latest_pkg = None
    if packages:
        p = packages[0]
        latest_pkg = OutcomePackageInfo(
            package_id=p.id,
            version=p.version,
            content_hash=p.content_hash,
            quality_status=p.quality_status,
            draft_count=p.draft_count,
            created_at=p.created_at,
        )

    package_summary = OutcomePackageSummary(
        count=len(packages),
        latest=latest_pkg,
    )

    # ── Runtime summary (minimal, from OntologyRuntimeAudit) ────────────
    runtime_count = db.scalar(
        select(func.count()).select_from(OntologyRuntimeAudit).where(
            OntologyRuntimeAudit.group_id == group_id,
            OntologyRuntimeAudit.project_id == project_id,
        )
    ) or 0

    last_runtime = db.scalars(
        select(OntologyRuntimeAudit)
        .where(
            OntologyRuntimeAudit.group_id == group_id,
            OntologyRuntimeAudit.project_id == project_id,
        )
        .order_by(OntologyRuntimeAudit.created_at.desc(), OntologyRuntimeAudit.id.desc())
        .limit(1)
    ).first()

    last_op = None
    if last_runtime is not None:
        last_op = {
            "operation": last_runtime.operation,
            "outcome": last_runtime.outcome,
            "created_at": last_runtime.created_at.isoformat()
            if last_runtime.created_at else None,
        }

    runtime_summary = OutcomeRuntimeSummary(
        total_operations=runtime_count,
        last_operation=last_op,
    )

    return PilotOutcomeSummaryResponse(
        project={
            "id": project.id,
            "name": project.name,
            "business_goal": project.business_goal,
            "stage": project.stage,
            "status": project.status,
        },
        latest_outcome=latest_outcome,
        evidence_summary=evidence_summary,
        package_summary=package_summary,
        runtime_summary=runtime_summary,
        decision_summary=decision_summary,
        risks=risks,
        next_actions=next_actions,
    )
