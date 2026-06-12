from dataclasses import dataclass
import re

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pgvector.sqlalchemy import Vector
from sqlalchemy import Float, bindparam, cast, or_, select
from sqlalchemy.orm import Session

from semantic_lighthouse.config import Settings, get_settings
from semantic_lighthouse.database import get_db
from semantic_lighthouse.dependencies import get_current_user, get_membership_or_404
from semantic_lighthouse.models import Document, DocumentChunk, RagRun, User
from semantic_lighthouse.schemas import (
    RagAnswerRequest,
    RagAnswerResponse,
    RagCitation,
    RagRunDetail,
    RagRunSummary,
)
from semantic_lighthouse.services.chat import ChatError, create_chat_client
from semantic_lighthouse.services.embeddings import EmbeddingError, cosine_similarity, create_embedding_client

from ._shared import PGVECTOR_DIMENSION, snippet, validate_pgvector_dimension

router = APIRouter(prefix="/groups/{group_id}/rag", tags=["rag"])


@dataclass(frozen=True)
class RetrievedChunk:
    chunk: DocumentChunk
    document: Document
    score: float | None
    retrieval_method: str


@router.post("/answer", response_model=RagAnswerResponse)
def answer_question(
    group_id: str,
    request: RagAnswerRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> RagAnswerResponse:
    get_membership_or_404(db, current_user.id, group_id)
    limit = request.limit or settings.rag_top_k
    retrieved, retrieval_method = _retrieve(db, group_id, request.question, request.retrieval_method, limit, settings)
    citations = _citations(retrieved, request.question, settings.rag_max_context_chars)
    if not citations:
        response = _no_evidence_response(request.question, retrieval_method)
        return _persist_rag_run(db, group_id, current_user.id, response)

    client = create_chat_client(settings)
    try:
        answer = client.answer_question(request.question, citations)
    except ChatError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    response = RagAnswerResponse(
        run_id="",
        question=request.question,
        answer=answer.answer,
        confidence=answer.confidence,
        knowledge_gaps=answer.knowledge_gaps,
        next_steps=answer.next_steps,
        citations=citations,
        retrieval_method=retrieval_method,
        model=answer.model,
    )
    return _persist_rag_run(db, group_id, current_user.id, response)


@router.get("/runs", response_model=list[RagRunSummary])
def list_rag_runs(
    group_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[RagRunSummary]:
    get_membership_or_404(db, current_user.id, group_id)
    runs = db.scalars(
        select(RagRun)
        .where(RagRun.group_id == group_id)
        .order_by(RagRun.created_at.desc())
        .limit(limit)
    ).all()
    return [_rag_run_summary(run) for run in runs]


@router.get("/runs/{run_id}", response_model=RagRunDetail)
def get_rag_run(
    group_id: str,
    run_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RagRunDetail:
    get_membership_or_404(db, current_user.id, group_id)
    run = db.scalar(select(RagRun).where(RagRun.id == run_id, RagRun.group_id == group_id))
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="RAG run not found")
    return _rag_run_detail(run)


def _no_evidence_response(question: str, retrieval_method: str) -> RagAnswerResponse:
    return RagAnswerResponse(
        run_id="",
        question=question,
        answer="The knowledge base did not return enough evidence to generate a reliable consulting answer.",
        confidence="low",
        knowledge_gaps=["No retrieved document chunk supports this question."],
        next_steps=[
            "Add relevant knowledge base documents and run retrieval again.",
            "Rewrite the question with terms closer to known entities or business scenarios.",
        ],
        citations=[],
        retrieval_method=retrieval_method,
        model="local-evidence-gate",
    )


def _persist_rag_run(
    db: Session,
    group_id: str,
    user_id: str,
    response: RagAnswerResponse,
) -> RagAnswerResponse:
    run = RagRun(
        group_id=group_id,
        user_id=user_id,
        question=response.question,
        answer=response.answer,
        confidence=response.confidence,
        retrieval_method=response.retrieval_method,
        model=response.model,
        citations=[citation.model_dump() for citation in response.citations],
        knowledge_gaps=response.knowledge_gaps,
        next_steps=response.next_steps,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return response.model_copy(update={"run_id": run.id})


def _rag_run_summary(run: RagRun) -> RagRunSummary:
    return RagRunSummary(
        id=run.id,
        group_id=run.group_id,
        user_id=run.user_id,
        question=run.question,
        confidence=run.confidence,
        retrieval_method=run.retrieval_method,
        model=run.model,
        citation_count=len(run.citations or []),
        created_at=run.created_at,
    )


def _rag_run_detail(run: RagRun) -> RagRunDetail:
    return RagRunDetail(
        id=run.id,
        group_id=run.group_id,
        user_id=run.user_id,
        question=run.question,
        answer=run.answer,
        confidence=run.confidence,
        knowledge_gaps=run.knowledge_gaps or [],
        next_steps=run.next_steps or [],
        citations=[RagCitation.model_validate(citation) for citation in run.citations or []],
        retrieval_method=run.retrieval_method,
        model=run.model,
        created_at=run.created_at,
    )


def _retrieve(
    db: Session,
    group_id: str,
    question: str,
    retrieval_method: str,
    limit: int,
    settings: Settings,
) -> tuple[list[RetrievedChunk], str]:
    if retrieval_method == "keyword":
        return _keyword_search(db, group_id, question, limit), "keyword"
    if retrieval_method == "semantic":
        try:
            return _semantic_search(db, group_id, question, limit, settings), "semantic"
        except EmbeddingError as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    if retrieval_method == "hybrid":
        from semantic_lighthouse.services.retrieval import hybrid_search as hs

        results = hs(db, group_id, question, limit, keyword_weight=0.3, settings=settings)
        return [
            RetrievedChunk(
                chunk=item.chunk, document=item.document,
                score=item.score, retrieval_method="hybrid",
            )
            for item in results
        ], "hybrid"

    # "auto" — try semantic first, fall back to keyword
    try:
        semantic_results = _semantic_search(db, group_id, question, limit, settings)
    except EmbeddingError:
        semantic_results = []
    if semantic_results:
        return semantic_results, "semantic"
    return _keyword_search(db, group_id, question, limit), "keyword"


def _keyword_search(db: Session, group_id: str, query: str, limit: int) -> list[RetrievedChunk]:
    terms = _keyword_terms(query)
    if not terms:
        return []
    search_conditions = [
        or_(
            DocumentChunk.content.ilike(f"%{term}%"),
            Document.title.ilike(f"%{term}%"),
            Document.source_path.ilike(f"%{term}%"),
        )
        for term in terms
    ]
    rows = db.execute(
        select(DocumentChunk, Document)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(
            DocumentChunk.group_id == group_id,
            Document.group_id == group_id,
            Document.status == "ready",
            or_(*search_conditions),
        )
        .order_by(Document.created_at.desc(), DocumentChunk.chunk_index.asc())
        .limit(limit)
    ).all()
    return [
        RetrievedChunk(chunk=chunk, document=document, score=None, retrieval_method="keyword")
        for chunk, document in rows
    ]


def _semantic_search(
    db: Session,
    group_id: str,
    query: str,
    limit: int,
    settings: Settings,
) -> list[RetrievedChunk]:
    validate_pgvector_dimension(db, settings)
    client = create_embedding_client(settings)
    query_vector = client.embed_texts([query]).vectors[0]
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        return _semantic_search_postgres(db, group_id, query_vector, limit)
    return _semantic_search_python(db, group_id, query_vector, limit)


def _semantic_search_python(
    db: Session,
    group_id: str,
    query_vector: list[float],
    limit: int,
) -> list[RetrievedChunk]:
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
        RetrievedChunk(chunk=chunk, document=document, score=score, retrieval_method="semantic")
        for score, chunk, document in scored[:limit]
    ]


def _semantic_search_postgres(
    db: Session,
    group_id: str,
    query_vector: list[float],
    limit: int,
) -> list[RetrievedChunk]:
    vector_literal = "[" + ",".join(str(float(item)) for item in query_vector) + "]"
    distance_expr = cast(
        DocumentChunk.embedding.op("<=>")(cast(bindparam("query_vector"), Vector(PGVECTOR_DIMENSION))),
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
        RetrievedChunk(
            chunk=chunk,
            document=document,
            score=1.0 - float(distance),
            retrieval_method="semantic",
        )
        for chunk, document, distance in rows
    ]


def _citations(retrieved: list[RetrievedChunk], query: str, max_context_chars: int) -> list[RagCitation]:
    citations: list[RagCitation] = []
    used_chars = 0
    for item in retrieved:
        frontmatter = item.document.frontmatter or {}
        chunk_snippet = snippet(item.chunk.content, query, radius=240)
        remaining = max_context_chars - used_chars
        if remaining <= 0:
            break
        chunk_snippet = chunk_snippet[:remaining].strip()
        used_chars += len(chunk_snippet)
        citations.append(
            RagCitation(
                document_id=item.document.id,
                chunk_id=item.chunk.id,
                title=item.document.title,
                source_path=item.document.source_path,
                file_name=item.document.file_name,
                chunk_index=item.chunk.chunk_index,
                heading_path=item.chunk.heading_path,
                snippet=chunk_snippet,
                entity_type=frontmatter.get("entityType"),
                document_type=frontmatter.get("documentType"),
                source=frontmatter.get("source"),
                status=frontmatter.get("status"),
                score=item.score,
                retrieval_method=item.retrieval_method,
            )
        )
    return citations


def _keyword_terms(query: str) -> list[str]:
    raw_terms = re.findall(r"[A-Za-z0-9_-]+|[\u4e00-\u9fff]{2,}", query)
    terms: list[str] = []
    for term in raw_terms:
        normalized = term.strip()
        if len(normalized) < 2:
            continue
        if normalized not in terms:
            terms.append(normalized)
    return terms[:8]
