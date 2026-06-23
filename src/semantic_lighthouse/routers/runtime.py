"""Phase 14.5 — Pilot Read Runtime router.

REST endpoints for ontology dataset binding generation,
unified read-only query, and pilot activation.

Member+ can read bindings and query. Owner/admin can
generate bindings and activate.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from semantic_lighthouse.database import get_db
from semantic_lighthouse.dependencies import (
    get_current_user,
    get_membership_or_404,
    require_group_role,
)
from semantic_lighthouse.models import User
from semantic_lighthouse.schemas import (
    RuntimeTraverseRequest,
    RuntimeTraverseResponse,
)
from semantic_lighthouse.services.runtime import (
    activate_pilot,
    execute_query,
    generate_bindings,
)
from semantic_lighthouse.services.runtime_traverse import execute_traversal

router = APIRouter(
    prefix="/groups/{group_id}/projects/{project_id}/runtime",
    tags=["runtime"],
)


# ── request / response schemas ────────────────────────────────────────────


class RuntimeQueryRequest(BaseModel):
    """Read-only query over bound dataset Object Types.

    No SQL, no DSL, no expression strings.
    Filter values are JSON scalars: string, integer, number, boolean, null.
    """

    object_type: str = Field(..., min_length=1)
    fields: list[str] | None = Field(default=None, max_length=100)
    filters: dict[str, str | int | float | bool | None] | None = Field(default=None)
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0, le=10000)
    explain_only: bool = Field(default=False)


class RuntimeQueryResponse(BaseModel):
    rows: list[dict]
    row_count: int | None
    explain: dict
    type_errors: list[dict] | None = None


class BindingGenerateResponse(BaseModel):
    created_count: int
    existing_count: int
    issues: list[dict]


class ActivateResponse(BaseModel):
    activated: bool
    already_pilot: bool
    stage: str
    issues: list[dict]


# ── project + stage validation helper ─────────────────────────────────────


def _get_project_and_validate_stage(
    db: Session, group_id: str, project_id: str, allowed_stages: set[str],
):
    """Load project, verify group ownership, check status and stage."""
    from semantic_lighthouse.models import BusinessProject

    project = db.get(BusinessProject, project_id)
    if project is None or project.group_id != group_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    if project.status != "active":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Project is archived",
        )
    if project.stage not in allowed_stages:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Project stage must be one of {allowed_stages}, "
                   f"currently: {project.stage}",
        )
    return project


# ═══════════════════════════════════════════════════════════════════════════
#  POST /runtime/bindings/generate — owner/admin only
# ═══════════════════════════════════════════════════════════════════════════


@router.post("/bindings/generate", response_model=BindingGenerateResponse)
def generate_dataset_bindings(
    group_id: str,
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BindingGenerateResponse:
    """Generate OntologyDatasetBindings from the latest project package.

    Owner or admin only. Project must be at validate or pilot stage.
    """
    require_group_role(db, current_user.id, group_id, {"owner", "admin"})
    _get_project_and_validate_stage(
        db, group_id, project_id, {"validate", "pilot"},
    )

    try:
        result = generate_bindings(db, group_id, project_id, current_user.id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc),
        ) from exc

    return BindingGenerateResponse(**result)


# ═══════════════════════════════════════════════════════════════════════════
#  GET /runtime/bindings — member+ read
# ═══════════════════════════════════════════════════════════════════════════


@router.get("/bindings")
def list_bindings(
    group_id: str,
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    """List active bindings for the latest project package. Member+."""
    get_membership_or_404(db, current_user.id, group_id)

    from sqlalchemy import select

    from semantic_lighthouse.models import BusinessProject, OntologyDatasetBinding
    from semantic_lighthouse.services.runtime import (
        _get_latest_project_package,
    )

    # Verify project exists and belongs to group
    project = db.get(BusinessProject, project_id)
    if project is None or project.group_id != group_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    pkg = _get_latest_project_package(db, group_id, project_id)
    if pkg is None:
        return []

    bindings = db.scalars(
        select(OntologyDatasetBinding).where(
            OntologyDatasetBinding.package_id == pkg.id,
            OntologyDatasetBinding.status == "active",
            OntologyDatasetBinding.group_id == group_id,
            OntologyDatasetBinding.project_id == project_id,
        )
    ).all()

    return [
        {
            "id": b.id,
            "package_id": b.package_id,
            "dataset_id": b.dataset_id,
            "object_type_api_name": b.object_type_api_name,
            "primary_key_column": b.primary_key_column,
            "property_mappings": b.property_mappings,
            "status": b.status,
            "created_by": b.created_by,
            "created_at": b.created_at.isoformat() if b.created_at else None,
            "updated_at": b.updated_at.isoformat() if b.updated_at else None,
        }
        for b in bindings
    ]


# ═══════════════════════════════════════════════════════════════════════════
#  POST /runtime/query — member+ read
# ═══════════════════════════════════════════════════════════════════════════


@router.post("/query", response_model=RuntimeQueryResponse)
def query_runtime(
    group_id: str,
    project_id: str,
    body: RuntimeQueryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RuntimeQueryResponse:
    """Execute a read-only query against bound dataset Object Types.

    Member+. No SQL, no DSL, no expression strings.
    Only equality filters on bound properties.
    """
    get_membership_or_404(db, current_user.id, group_id)

    # Project must exist and be active
    from semantic_lighthouse.models import BusinessProject

    project = db.get(BusinessProject, project_id)
    if project is None or project.group_id != group_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    if project.status != "active":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Project is archived",
        )

    # Pass filter values as native JSON scalars — service handles type conversion
    native_filters: dict[str, str | int | float | bool | None] | None = None
    if body.filters:
        native_filters = dict(body.filters)

    try:
        result = execute_query(
            db,
            group_id=group_id,
            project_id=project_id,
            object_type=body.object_type,
            user_id=current_user.id,
            fields=body.fields,
            filters=native_filters,
            limit=body.limit,
            offset=body.offset,
            explain_only=body.explain_only,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    if result.get("type_errors"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "Type conversion errors in query results",
                "type_errors": result["type_errors"],
            },
        )

    return RuntimeQueryResponse(**result)


# POST /runtime/traverse: member+ read (single-hop traversal).


@router.post("/traverse", response_model=RuntimeTraverseResponse)
def traverse_runtime(
    group_id: str,
    project_id: str,
    body: RuntimeTraverseRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RuntimeTraverseResponse:
    """Execute a 1-2 hop relationship traversal over bound datasets.

    Member+. Only package-declared link_types. No SQL, no DSL.
    Filters accepted on any OT in the path (AND within each OT).
    """
    get_membership_or_404(db, current_user.id, group_id)

    # Project must exist and be active
    from semantic_lighthouse.models import BusinessProject

    project = db.get(BusinessProject, project_id)
    if project is None or project.group_id != group_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    if project.status != "active":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Project is archived",
        )

    # Pass all per-OT filters through — service validates per OT.
    native_filters: dict[str, dict[str, str | int | float | bool | None]] | None = None
    if body.filters:
        native_filters = {
            ot: dict(ot_filters) for ot, ot_filters in body.filters.items()
        }

    try:
        result = execute_traversal(
            db,
            group_id=group_id,
            project_id=project_id,
            path=body.path,
            user_id=current_user.id,
            fields=body.fields,
            filters=native_filters,
            limit=body.limit,
            offset=body.offset,
            explain_only=body.explain_only,
            response_shape=body.response_shape,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    if result.get("type_errors"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "Type conversion errors in traversal results",
                "type_errors": result["type_errors"],
            },
        )

    return RuntimeTraverseResponse(**result)


# ═══════════════════════════════════════════════════════════════════════════
#  POST /runtime/activate — owner/admin only
# ═══════════════════════════════════════════════════════════════════════════


@router.post("/activate", response_model=ActivateResponse)
def activate_pilot_stage(
    group_id: str,
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ActivateResponse:
    """Activate the pilot stage for a project.

    Owner or admin only. Project must be at validate or pilot stage.
    All dataset-grounded Object Types must have valid bindings.
    Smoke query must pass for each binding.
    """
    require_group_role(db, current_user.id, group_id, {"owner", "admin"})
    _get_project_and_validate_stage(
        db, group_id, project_id, {"validate", "pilot"},
    )

    try:
        result = activate_pilot(db, group_id, project_id, current_user.id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc),
        ) from exc

    if not result["activated"] and not result["already_pilot"]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "Activation failed. Review issues for details.",
                "issues": result["issues"],
            },
        )

    return ActivateResponse(**result)
