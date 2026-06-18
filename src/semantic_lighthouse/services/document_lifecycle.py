"""Shared document lifecycle helpers.

Both the REST endpoint and the Agent tool path must go through these helpers
so that audit fields (archived_by, archived_at, archive_reason) are always set
and group_id isolation is always checked.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from semantic_lighthouse.models import Document, utc_now


def archive_document(
    db: Session,
    document: Document,
    group_id: str,
    actor_user_id: str,
    reason: str,
) -> None:
    if document.group_id != group_id:
        raise ValueError("Document does not belong to this group")
    if document.status not in ("ready", "failed"):
        raise ValueError(
            f"Cannot archive document with status '{document.status}'"
        )
    document.status = "archived"
    document.archived_by = actor_user_id
    document.archived_at = utc_now()
    document.archive_reason = reason
    db.commit()
