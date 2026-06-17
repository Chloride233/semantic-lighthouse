"""Lightweight tasks — user-confirmed next steps from RAG answers.

Product alignment §7: tasks are traceable work items, not a full PM system.
V1: only source_type='rag_run'. No DELETE endpoint.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from semantic_lighthouse.database import get_db
from semantic_lighthouse.dependencies import get_current_user, get_membership_or_404
from semantic_lighthouse.models import Task, User
from semantic_lighthouse.schemas import (
    TaskCreateRequest,
    TaskListResponse,
    TaskResponse,
    TaskUpdateRequest,
)

router = APIRouter(prefix="/groups/{group_id}/tasks", tags=["tasks"])


def _task_response(task: Task) -> TaskResponse:
    return TaskResponse(
        id=task.id,
        group_id=task.group_id,
        title=task.title,
        description=task.description,
        status=task.status,
        source_type=task.source_type,
        source_id=task.source_id,
        created_by=task.created_by,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


@router.post("", status_code=status.HTTP_201_CREATED, response_model=TaskResponse)
def create_task(
    body: TaskCreateRequest,
    group_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TaskResponse:
    """Confirm a RAG next_step into a lightweight task."""
    get_membership_or_404(db, current_user.id, group_id)

    task = Task(
        group_id=group_id,
        title=body.title,
        description=body.description,
        status="pending",
        source_type=body.source_type,
        source_id=body.source_id,
        created_by=current_user.id,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return _task_response(task)


@router.get("", response_model=TaskListResponse)
def list_tasks(
    group_id: str,
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TaskListResponse:
    """List group-scoped tasks with optional status filter."""
    get_membership_or_404(db, current_user.id, group_id)

    base = select(Task).where(Task.group_id == group_id)
    if status_filter:
        base = base.where(Task.status == status_filter)

    total = db.scalar(select(func.count()).select_from(base.subquery()))
    tasks = db.scalars(
        base.order_by(Task.created_at.desc()).offset(offset).limit(limit)
    ).all()

    return TaskListResponse(
        tasks=[_task_response(t) for t in tasks],
        total=total or 0,
    )


@router.get("/{task_id}", response_model=TaskResponse)
def get_task(
    task_id: str,
    group_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TaskResponse:
    """Get a single task detail."""
    get_membership_or_404(db, current_user.id, group_id)

    task = db.get(Task, task_id)
    if task is None or task.group_id != group_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return _task_response(task)


@router.patch("/{task_id}", response_model=TaskResponse)
def update_task(
    task_id: str,
    body: TaskUpdateRequest,
    group_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TaskResponse:
    """Update task status (any member) or title/description (creator only)."""
    get_membership_or_404(db, current_user.id, group_id)

    task = db.get(Task, task_id)
    if task is None or task.group_id != group_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    if body.status is not None:
        task.status = body.status

    if body.title is not None or body.description is not None:
        if task.created_by != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the task creator can edit the title or description",
            )

    if body.title is not None:
        task.title = body.title
    if body.description is not None:
        task.description = body.description

    db.commit()
    db.refresh(task)
    return _task_response(task)
