"""Shared router helpers — keep duplication out of individual route modules."""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from semantic_lighthouse.config import Settings

PGVECTOR_DIMENSION = 1024


def validate_pgvector_dimension(db: Session, settings: Settings) -> None:
    """Raise 500 if configured embedding dimension does not match pgvector DDL."""
    if db.bind is None or db.bind.dialect.name != "postgresql":
        return
    if settings.embedding_dimension != PGVECTOR_DIMENSION:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                f"PostgreSQL pgvector dimension is {PGVECTOR_DIMENSION}; "
                f"EMBEDDING_DIMENSION is {settings.embedding_dimension}"
            ),
        )


def snippet(content: str, query: str, *, radius: int = 80) -> str:
    """Return a window of *content* around the first occurrence of *query*."""
    lowered = content.lower()
    position = lowered.find(query.lower())
    if position < 0:
        return content[: radius * 2].strip()
    start = max(position - radius, 0)
    end = min(position + len(query) + radius, len(content))
    return content[start:end].strip()
