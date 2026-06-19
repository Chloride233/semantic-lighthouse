"""Atomic human review transitions for ontology modeling drafts."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from semantic_lighthouse.models import OntologyModelingDraft, utc_now


class DraftReviewError(Exception):
    """A review request cannot be applied atomically."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def review_modeling_drafts(
    db: Session,
    group_id: str,
    draft_ids: list[str],
    decision: str,
    reviewer_id: str,
    review_note: str | None = None,
) -> tuple[list[OntologyModelingDraft], datetime]:
    """Accept or reject proposed drafts as one group-scoped transaction."""
    unique_ids = list(dict.fromkeys(draft_ids))
    drafts = list(
        db.scalars(
            select(OntologyModelingDraft).where(
                OntologyModelingDraft.id.in_(unique_ids),
                OntologyModelingDraft.group_id == group_id,
            )
        ).all()
    )

    if len(drafts) != len(unique_ids):
        raise DraftReviewError(
            code="draft_not_found",
            message="One or more drafts not found in this group",
        )

    if any(draft.status != "proposed" for draft in drafts):
        raise DraftReviewError(
            code="draft_already_reviewed",
            message="One or more drafts have already been reviewed",
        )

    cleaned_note = review_note.strip() if review_note else None
    now = utc_now()
    for draft in drafts:
        draft.status = decision
        draft.reviewed_by = reviewer_id
        draft.reviewed_at = now
        draft.review_note = cleaned_note
        draft.updated_at = now

    db.commit()
    return drafts, now
