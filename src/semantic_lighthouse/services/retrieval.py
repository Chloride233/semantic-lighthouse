"""Retrieval strategies: keyword, semantic, and hybrid fusion.

Hybrid search fuses keyword + vector results with configurable weights,
reusing existing queries rather than introducing new SQL or indexes.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import Float, cast, select
from sqlalchemy.orm import Session

from semantic_lighthouse.config import Settings
from semantic_lighthouse.models import Document, DocumentChunk
from semantic_lighthouse.services.embeddings import EmbeddingError, cosine_similarity, create_embedding_client

logger = logging.getLogger(__name__)

_PGVECTOR_DIMENSION = 1024


@dataclass(frozen=True)
class ScoredChunk:
    chunk: DocumentChunk
    document: Document
    score: float
    retrieval_method: str


# ── public API ─────────────────────────────────────────────────────────────


def hybrid_search(
    db: Session,
    group_id: str,
    query: str,
    limit: int,
    keyword_weight: float,
    settings: Settings,
) -> list[ScoredChunk]:
    """Fuse keyword and semantic results with linear score combination.

    Each method's raw scores are min-max normalized within its result
    set so both contribute on a 0–1 scale.  Duplicate chunks (appearing
    in both sets) keep the higher fused score.
    """
    kw_chunks = _keyword_search(db, group_id, query, limit * 2)
    sem_chunks = _semantic_search(db, group_id, query, limit * 2, settings)

    seen: dict[str, ScoredChunk] = {}
    _merge_scored(seen, kw_chunks, keyword_weight)
    _merge_scored(seen, sem_chunks, 1.0 - keyword_weight)

    merged = sorted(seen.values(), key=lambda c: c.score, reverse=True)
    return merged[:limit]


# ── keyword ────────────────────────────────────────────────────────────────


def _keyword_search(db: Session, group_id: str, query: str, limit: int) -> list[ScoredChunk]:
    rows = db.execute(
        select(DocumentChunk, Document)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(
            DocumentChunk.group_id == group_id,
            Document.group_id == group_id,
            Document.status == "ready",
            DocumentChunk.content.ilike(f"%{query}%"),
        )
        .order_by(Document.created_at.desc(), DocumentChunk.chunk_index.asc())
        .limit(limit)
    ).all()

    raw_scores = [_keyword_match_count(chunk.content, query) for chunk, _doc in rows]
    max_raw = max(raw_scores) if raw_scores else 1.0

    return [
        ScoredChunk(
            chunk=chunk,
            document=doc,
            score=raw / max_raw if max_raw > 0 else 0.0,
            retrieval_method="keyword",
        )
        for (chunk, doc), raw in zip(rows, raw_scores)
    ]


def _keyword_match_count(content: str, query: str) -> float:
    lowered = content.lower()
    q = query.lower()
    count = 0
    pos = 0
    while True:
        pos = lowered.find(q, pos)
        if pos < 0:
            break
        count += 1
        pos += max(len(q), 1)
    return float(count)


# ── semantic ───────────────────────────────────────────────────────────────


def _semantic_search(
    db: Session, group_id: str, query: str, limit: int, settings: Settings
) -> list[ScoredChunk]:
    client = create_embedding_client(settings)
    try:
        query_vector = client.embed_texts([query]).vectors[0]
    except EmbeddingError:
        logger.warning("Embedding failed for query; semantic contribution skipped")
        return []

    if db.bind is not None and db.bind.dialect.name == "postgresql":
        return _semantic_postgres(db, group_id, query_vector, limit)
    return _semantic_python(db, group_id, query_vector, limit)


def _semantic_python(
    db: Session, group_id: str, query_vector: list[float], limit: int
) -> list[ScoredChunk]:
    rows = db.execute(
        select(DocumentChunk, Document)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(
            DocumentChunk.group_id == group_id,
            Document.group_id == group_id,
            Document.status == "ready",
            DocumentChunk.embedding.is_not(None),
        )
    ).all()

    scored = [
        (cosine_similarity(query_vector, chunk.embedding or []), chunk, document)
        for chunk, document in rows
    ]
    scored.sort(key=lambda item: item[0], reverse=True)
    return [
        ScoredChunk(chunk=chunk, document=doc, score=max(sim, 0.0), retrieval_method="semantic")
        for sim, chunk, doc in scored[:limit]
    ]


def _semantic_postgres(
    db: Session, group_id: str, query_vector: list[float], limit: int
) -> list[ScoredChunk]:
    from pgvector.sqlalchemy import Vector
    from sqlalchemy import bindparam

    vector_literal = "[" + ",".join(str(float(v)) for v in query_vector) + "]"
    distance_expr = cast(
        DocumentChunk.embedding.op("<=>")(
            cast(bindparam("query_vector"), Vector(_PGVECTOR_DIMENSION))
        ),
        Float,
    ).label("distance")

    rows = db.execute(
        select(DocumentChunk, Document, distance_expr)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(
            DocumentChunk.group_id == group_id,
            Document.group_id == group_id,
            Document.status == "ready",
            DocumentChunk.embedding.is_not(None),
        )
        .order_by(distance_expr.asc())
        .limit(limit)
        .params(query_vector=vector_literal)
    ).all()

    return [
        ScoredChunk(
            chunk=chunk, document=doc,
            score=max(1.0 - float(distance), 0.0),
            retrieval_method="semantic",
        )
        for chunk, doc, distance in rows
    ]


# ── fusion ─────────────────────────────────────────────────────────────────


def _merge_scored(
    seen: dict[str, ScoredChunk],
    items: list[ScoredChunk],
    weight: float,
) -> None:
    """Merge *items* into *seen* with *weight*, keeping higher score on dup."""
    for item in items:
        fused = item.score * weight
        if item.chunk.id in seen:
            if fused > seen[item.chunk.id].score:
                seen[item.chunk.id] = ScoredChunk(
                    chunk=item.chunk, document=item.document,
                    score=fused, retrieval_method="hybrid",
                )
        else:
            seen[item.chunk.id] = ScoredChunk(
                chunk=item.chunk, document=item.document,
                score=fused, retrieval_method="hybrid",
            )
