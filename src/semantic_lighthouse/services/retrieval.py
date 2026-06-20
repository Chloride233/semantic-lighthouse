"""Retrieval strategies: keyword, semantic, and hybrid fusion.

Hybrid search fuses keyword + vector results with configurable weights,
reusing existing queries rather than introducing new SQL or indexes.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from sqlalchemy import Float, case, cast, or_, select
from sqlalchemy.orm import Session

from semantic_lighthouse.config import Settings
from semantic_lighthouse.models import Document, DocumentChunk
from semantic_lighthouse.routers._shared import PGVECTOR_DIMENSION
from semantic_lighthouse.services.embeddings import EmbeddingError, cosine_similarity, create_embedding_client

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ScoredChunk:
    chunk: DocumentChunk
    document: Document
    score: float
    retrieval_method: str


def project_document_ids(db: Session, group_id: str, project_id: str | None) -> set[str] | None:
    """Derive allowed Document IDs from active ProjectEvidenceLinks.

    Returns None for unscoped (full group access). Returns empty set when
    project has no linked documents (must not fall back to group scope).
    """
    if project_id is None:
        return None
    from semantic_lighthouse.models import ProjectEvidenceLink
    rows = db.execute(
        select(ProjectEvidenceLink.evidence_id).where(
            ProjectEvidenceLink.group_id == group_id,
            ProjectEvidenceLink.project_id == project_id,
            ProjectEvidenceLink.evidence_type == "document",
            ProjectEvidenceLink.status == "active",
        )
    ).all()
    return {row[0] for row in rows}


# ── public API ─────────────────────────────────────────────────────────────


def hybrid_search(
    db: Session,
    group_id: str,
    query: str,
    limit: int,
    keyword_weight: float,
    settings: Settings,
    allowed_document_ids: set[str] | None = None,
) -> list[ScoredChunk]:
    """Fuse keyword and semantic results with linear score combination.

    Each method's raw scores are min-max normalized within its result
    set so both contribute on a 0–1 scale.  Duplicate chunks (appearing
    in both sets) keep the higher fused score.

    allowed_document_ids: None = all group docs. Empty set = no results.
    """
    kw_chunks = _keyword_search(db, group_id, query, limit * 2, allowed_document_ids=allowed_document_ids)
    sem_chunks = _semantic_search(db, group_id, query, limit * 2, settings, allowed_document_ids=allowed_document_ids)

    seen: dict[str, ScoredChunk] = {}
    _merge_scored(seen, kw_chunks, keyword_weight)
    _merge_scored(seen, sem_chunks, 1.0 - keyword_weight)

    merged = sorted(seen.values(), key=lambda c: c.score, reverse=True)
    return merged[:limit]


# ── keyword ────────────────────────────────────────────────────────────────


def _keyword_search(db: Session, group_id: str, query: str, limit: int, *, allowed_document_ids: set[str] | None = None) -> list[ScoredChunk]:
    if allowed_document_ids is not None and not allowed_document_ids:
        return []  # empty evidence set → no results, never fall back
    terms = _keyword_terms(query)
    if not terms:
        return []

    search_conditions = [
        or_(
            DocumentChunk.content.ilike(f"%{term}%"),
            DocumentChunk.heading_path.ilike(f"%{term}%"),
            Document.title.ilike(f"%{term}%"),
            Document.source_path.ilike(f"%{term}%"),
        )
        for term in terms
    ]
    relevance = _keyword_relevance_expr(terms)
    where_clauses = [
        DocumentChunk.group_id == group_id,
        Document.group_id == group_id,
        Document.status == "ready",
        or_(*search_conditions),
    ]
    if allowed_document_ids is not None:
        where_clauses.append(DocumentChunk.document_id.in_(allowed_document_ids))
    rows = db.execute(
        select(DocumentChunk, Document, relevance.label("relevance"))
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(*where_clauses)
        .order_by(relevance.desc(), Document.created_at.desc(), DocumentChunk.chunk_index.asc())
        .limit(limit)
    ).all()

    raw_scores = [float(relevance_value or 0) for _chunk, _doc, relevance_value in rows]
    max_raw = max(raw_scores) if raw_scores else 1.0

    return [
        ScoredChunk(
            chunk=chunk,
            document=doc,
            score=raw / max_raw if max_raw > 0 else 0.0,
            retrieval_method="keyword",
        )
        for (chunk, doc, _relevance), raw in zip(rows, raw_scores)
        if raw > 0
    ]


def _keyword_relevance_expr(terms: list[str]):
    ascii_pattern = re.compile(r"[A-Za-z0-9_-]")
    relevance = case((DocumentChunk.content.ilike(f"%{terms[0]}%"), 2), else_=0)
    relevance = relevance + case((Document.title.ilike(f"%{terms[0]}%"), 2), else_=0)
    relevance = relevance + case((DocumentChunk.heading_path.ilike(f"%{terms[0]}%"), 1), else_=0)
    relevance = relevance + case((Document.source_path.ilike(f"%{terms[0]}%"), 1), else_=0)
    if ascii_pattern.search(terms[0]):
        relevance = relevance + case((DocumentChunk.content.ilike(f"%{terms[0]}%"), 1), else_=0)

    for term in terms[1:]:
        content_weight = 3 if ascii_pattern.search(term) else 2
        relevance = relevance + case((DocumentChunk.content.ilike(f"%{term}%"), content_weight), else_=0)
        relevance = relevance + case((Document.title.ilike(f"%{term}%"), 2), else_=0)
        relevance = relevance + case((DocumentChunk.heading_path.ilike(f"%{term}%"), 1), else_=0)
        relevance = relevance + case((Document.source_path.ilike(f"%{term}%"), 1), else_=0)
    return relevance


def _keyword_terms(query: str) -> list[str]:
    raw_terms = re.findall(r"[A-Za-z0-9_-]+|[\u4e00-\u9fff]{2,}", query)
    ascii_terms: list[str] = []
    cjk_terms: list[str] = []
    for term in raw_terms:
        normalized = term.strip()
        if len(normalized) < 2:
            continue
        if re.fullmatch(r"[\u4e00-\u9fff]{3,}", normalized):
            for i in range(len(normalized) - 1):
                bigram = normalized[i : i + 2]
                if bigram not in cjk_terms:
                    cjk_terms.append(bigram)
        elif normalized not in ascii_terms:
            ascii_terms.append(normalized)
    return (ascii_terms + cjk_terms)[:8]


# ── semantic ───────────────────────────────────────────────────────────────


def _semantic_search(
    db: Session, group_id: str, query: str, limit: int, settings: Settings, *, allowed_document_ids: set[str] | None = None,
) -> list[ScoredChunk]:
    if allowed_document_ids is not None and not allowed_document_ids:
        return []
    client = create_embedding_client(settings)
    try:
        query_vector = client.embed_texts([query]).vectors[0]
    except EmbeddingError:
        logger.warning("Embedding failed for query; semantic contribution skipped")
        return []
    return _semantic_search_with_vector(db, group_id, query_vector, limit, allowed_document_ids=allowed_document_ids)


def _semantic_search_with_vector(
    db: Session, group_id: str, query_vector: list[float], limit: int, *, allowed_document_ids: set[str] | None = None,
) -> list[ScoredChunk]:
    """Run semantic search with a pre-computed query vector (caller handles errors)."""
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        return _semantic_postgres(db, group_id, query_vector, limit, allowed_document_ids=allowed_document_ids)
    return _semantic_python(db, group_id, query_vector, limit, allowed_document_ids=allowed_document_ids)


def _semantic_python(
    db: Session, group_id: str, query_vector: list[float], limit: int, *, allowed_document_ids: set[str] | None = None,
) -> list[ScoredChunk]:
    where_clauses = [
        DocumentChunk.group_id == group_id,
        Document.group_id == group_id,
        Document.status == "ready",
        DocumentChunk.embedding.is_not(None),
    ]
    if allowed_document_ids is not None:
        where_clauses.append(DocumentChunk.document_id.in_(allowed_document_ids))
    rows = db.execute(
        select(DocumentChunk, Document)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(*where_clauses)
    ).all()

    scored = []
    for chunk, document in rows:
        if not chunk.embedding:
            continue
        similarity = cosine_similarity(query_vector, chunk.embedding)
        scored.append((similarity, chunk, document))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [
        ScoredChunk(chunk=chunk, document=doc, score=max(sim, 0.0), retrieval_method="semantic")
        for sim, chunk, doc in scored[:limit]
    ]


def _semantic_postgres(
    db: Session, group_id: str, query_vector: list[float], limit: int, *, allowed_document_ids: set[str] | None = None,
) -> list[ScoredChunk]:
    from pgvector.sqlalchemy import Vector
    from sqlalchemy import bindparam

    vector_literal = "[" + ",".join(str(float(v)) for v in query_vector) + "]"
    distance_expr = cast(
        DocumentChunk.embedding.op("<=>")(
            cast(bindparam("query_vector"), Vector(PGVECTOR_DIMENSION))
        ),
        Float,
    ).label("distance")

    where_clauses = [
        DocumentChunk.group_id == group_id,
        Document.group_id == group_id,
    ]
    if allowed_document_ids is not None:
        where_clauses.append(DocumentChunk.document_id.in_(allowed_document_ids))
    where_clauses.append(Document.status == "ready")
    where_clauses.append(DocumentChunk.embedding.is_not(None))
    rows = db.execute(
        select(DocumentChunk, Document, distance_expr)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(*where_clauses)
        .order_by(distance_expr.asc())
        .limit(limit)
        .params(query_vector=vector_literal)
    ).all()

    results: list[ScoredChunk] = []
    for chunk, doc, distance in rows:
        score = max(1.0 - float(distance), 0.0)
        results.append(
            ScoredChunk(
                chunk=chunk, document=doc,
                score=score,
                retrieval_method="semantic",
            )
        )
    return results


# ── fusion ─────────────────────────────────────────────────────────────────


def _merge_scored(
    seen: dict[str, ScoredChunk],
    items: list[ScoredChunk],
    weight: float,
) -> None:
    """Merge *items* into *seen* with *weight*, keeping higher score on dup."""
    for item in items:
        fused = item.score * weight
        if fused <= 0:
            continue
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
