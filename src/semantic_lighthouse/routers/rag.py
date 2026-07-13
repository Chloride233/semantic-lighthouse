from dataclasses import dataclass
import re
import time

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import case, or_, select
from sqlalchemy.orm import Session

from semantic_lighthouse.config import Settings, get_settings
from semantic_lighthouse.database import get_db
from semantic_lighthouse.dependencies import get_current_user, get_membership_or_404
from semantic_lighthouse.models import BusinessProject, Document, DocumentChunk, RagRun, User
from semantic_lighthouse.schemas import (
    RagAnswerRequest,
    RagAnswerResponse,
    RagCitation,
    RagRunDetail,
    RagRunSummary,
)
from semantic_lighthouse.services.chat import ChatError, adjusted_confidence, compute_evidence_quality, create_chat_client, sanitize_references
from semantic_lighthouse.services.embeddings import EmbeddingError, create_embedding_client
from semantic_lighthouse.services.retrieval import project_document_ids

from ._shared import snippet, validate_pgvector_dimension

router = APIRouter(prefix="/groups/{group_id}/rag", tags=["rag"])
project_router = APIRouter(prefix="/groups/{group_id}/projects/{project_id}/rag", tags=["rag"])


@dataclass(frozen=True)
class RetrievedChunk:
    chunk: DocumentChunk
    document: Document
    score: float | None
    retrieval_method: str


MAX_CITATIONS_PER_DOCUMENT_FIRST_PASS = 2


def _elapsed_ms(started_at: float) -> int:
    return max(1, int((time.monotonic() - started_at) * 1000))


@router.post("/answer", response_model=RagAnswerResponse)
def answer_question(
    group_id: str,
    request: RagAnswerRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> RagAnswerResponse:
    get_membership_or_404(db, current_user.id, group_id)
    return _answer_question_in_scope(
        db,
        settings,
        group_id,
        current_user.id,
        request,
        project_id=None,
        allowed_document_ids=None,
    )


@project_router.post("/answer", response_model=RagAnswerResponse)
def answer_project_question(
    group_id: str,
    project_id: str,
    request: RagAnswerRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> RagAnswerResponse:
    get_membership_or_404(db, current_user.id, group_id)
    project = db.get(BusinessProject, project_id)
    if project is None or project.group_id != group_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    if project.status == "archived":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Archived projects cannot create project-scoped RAG answers",
        )

    allowed_document_ids = project_document_ids(db, group_id, project_id)
    return _answer_question_in_scope(
        db,
        settings,
        group_id,
        current_user.id,
        request,
        project_id=project_id,
        allowed_document_ids=allowed_document_ids,
    )


def _answer_question_in_scope(
    db: Session,
    settings: Settings,
    group_id: str,
    user_id: str,
    request: RagAnswerRequest,
    *,
    project_id: str | None,
    allowed_document_ids: set[str] | None,
) -> RagAnswerResponse:
    t0 = time.monotonic()
    limit = request.limit or settings.rag_top_k
    retrieved, retrieval_method = _retrieve(
        db,
        group_id,
        request.question,
        request.retrieval_method,
        limit,
        settings,
        allowed_document_ids=allowed_document_ids,
    )
    citations = _citations(retrieved, request.question, settings.rag_max_context_chars)

    if not citations:
        response = _no_evidence_response(request.question, retrieval_method)
        duration_ms = _elapsed_ms(t0)
        return _persist_rag_run(
            db,
            group_id,
            user_id,
            response,
            project_id=project_id,
            status="no_evidence",
            duration_ms=duration_ms,
            retrieved_count=len(retrieved),
        )

    client = create_chat_client(settings)
    try:
        answer = client.answer_question(request.question, citations)
    except ChatError as exc:
        duration_ms = _elapsed_ms(t0)
        try:
            _persist_failed_run(
                db,
                group_id,
                user_id,
                request.question,
                citations,
                retrieval_method,
                str(exc),
                duration_ms,
                len(retrieved),
                project_id=project_id,
            )
        except Exception:
            # Audit persistence failure must not mask the original ChatError.
            pass
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    sanitized = sanitize_references(answer.answer, citations)
    confidence, confidence_reason = adjusted_confidence(answer.confidence, citations)
    evidence_quality = compute_evidence_quality(citations)

    response = RagAnswerResponse(
        run_id="",
        question=request.question,
        answer=sanitized,
        confidence=confidence,
        confidence_reason=confidence_reason,
        evidence_quality=evidence_quality,
        knowledge_gaps=answer.knowledge_gaps,
        next_steps=answer.next_steps,
        citations=citations,
        retrieval_method=retrieval_method,
        model=answer.model,
    )
    duration_ms = _elapsed_ms(t0)
    return _persist_rag_run(
        db,
        group_id,
        user_id,
        response,
        project_id=project_id,
        status="success",
        duration_ms=duration_ms,
        retrieved_count=len(retrieved),
    )


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
        answer="当前知识库没有返回足够证据，无法生成可靠的咨询式回答。",
        confidence="low",
        confidence_reason="未检索到任何可用证据片段，无法生成可靠回答。建议补充知识库文档或改写问题。",
        evidence_quality=compute_evidence_quality([]),
        knowledge_gaps=["没有检索到能够支撑该问题的文档片段。"],
        next_steps=[
            "补充相关知识库文档后重新检索。",
            "将问题改写为更贴近已知实体、业务场景或方法论的表达。",
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
    *,
    project_id: str | None = None,
    status: str = "success",
    duration_ms: int | None = None,
    retrieved_count: int | None = None,
) -> RagAnswerResponse:
    run = RagRun(
        group_id=group_id,
        user_id=user_id,
        project_id=project_id,
        question=response.question,
        answer=response.answer,
        confidence=response.confidence,
        retrieval_method=response.retrieval_method,
        model=response.model,
        citations=[citation.model_dump() for citation in response.citations],
        knowledge_gaps=response.knowledge_gaps,
        next_steps=response.next_steps,
        status=status,
        duration_ms=duration_ms,
        retrieved_count=retrieved_count,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return response.model_copy(update={"run_id": run.id})


def _persist_failed_run(
    db: Session,
    group_id: str,
    user_id: str,
    question: str,
    citations: list[RagCitation],
    retrieval_method: str,
    error_message: str,
    duration_ms: int,
    retrieved_count: int,
    *,
    project_id: str | None = None,
) -> None:
    run = RagRun(
        group_id=group_id,
        user_id=user_id,
        project_id=project_id,
        question=question,
        answer="RAG 回答生成失败，详见 error_message。",
        confidence="low",
        retrieval_method=retrieval_method,
        model="error",
        citations=[citation.model_dump() for citation in citations],
        knowledge_gaps=[],
        next_steps=[],
        status="error",
        error_message=error_message,
        duration_ms=duration_ms,
        retrieved_count=retrieved_count,
    )
    db.add(run)
    db.commit()


def _rag_run_summary(run: RagRun) -> RagRunSummary:
    return RagRunSummary(
        id=run.id,
        group_id=run.group_id,
        user_id=run.user_id,
        project_id=run.project_id,
        question=run.question,
        confidence=run.confidence,
        retrieval_method=run.retrieval_method,
        model=run.model,
        citation_count=len(run.citations or []),
        status=run.status,
        duration_ms=run.duration_ms,
        created_at=run.created_at,
    )


def _rag_run_detail(run: RagRun) -> RagRunDetail:
    stored_citations = [RagCitation.model_validate(c) for c in run.citations or []]
    _, reason = adjusted_confidence(run.confidence, stored_citations)
    evidence_quality = compute_evidence_quality(stored_citations)
    return RagRunDetail(
        id=run.id,
        group_id=run.group_id,
        user_id=run.user_id,
        project_id=run.project_id,
        question=run.question,
        answer=run.answer,
        confidence=run.confidence,
        confidence_reason=reason,
        evidence_quality=evidence_quality,
        knowledge_gaps=run.knowledge_gaps or [],
        next_steps=run.next_steps or [],
        citations=stored_citations,
        retrieval_method=run.retrieval_method,
        model=run.model,
        status=run.status,
        error_message=run.error_message,
        duration_ms=run.duration_ms,
        retrieved_count=run.retrieved_count,
        created_at=run.created_at,
    )


def _retrieve(
    db: Session,
    group_id: str,
    question: str,
    retrieval_method: str,
    limit: int,
    settings: Settings,
    *,
    allowed_document_ids: set[str] | None = None,
) -> tuple[list[RetrievedChunk], str]:
    if retrieval_method == "keyword":
        return _keyword_search(
            db, group_id, question, limit, allowed_document_ids=allowed_document_ids
        ), "keyword"
    if retrieval_method == "semantic":
        try:
            return _semantic_search(
                db,
                group_id,
                question,
                limit,
                settings,
                allowed_document_ids=allowed_document_ids,
            ), "semantic"
        except EmbeddingError as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    if retrieval_method == "hybrid":
        from semantic_lighthouse.services.retrieval import hybrid_search as hs

        results = hs(
            db,
            group_id,
            question,
            limit,
            keyword_weight=0.3,
            settings=settings,
            allowed_document_ids=allowed_document_ids,
        )
        return [
            RetrievedChunk(
                chunk=item.chunk, document=item.document,
                score=item.score, retrieval_method="hybrid",
            )
            for item in results
        ], "hybrid"

    # "auto" — try semantic first, fall back to keyword
    try:
        semantic_results = _semantic_search(
            db,
            group_id,
            question,
            limit,
            settings,
            allowed_document_ids=allowed_document_ids,
        )
    except EmbeddingError:
        semantic_results = []
    if semantic_results:
        return semantic_results, "semantic"
    return _keyword_search(
        db, group_id, question, limit, allowed_document_ids=allowed_document_ids
    ), "keyword"


def _keyword_search(
    db: Session,
    group_id: str,
    query: str,
    limit: int,
    *,
    allowed_document_ids: set[str] | None = None,
) -> list[RetrievedChunk]:
    if allowed_document_ids is not None and not allowed_document_ids:
        return []
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
    # Relevance: count how many search terms appear in the chunk content.
    # ASCII/numeric terms are weighted ×2 — they're more discriminative than
    # Chinese bi-grams which appear in almost every document.
    ascii_pattern = re.compile(r"[A-Za-z0-9_-]")
    relevance = case((DocumentChunk.content.ilike(f"%{terms[0]}%"), 1), else_=0)
    if ascii_pattern.search(terms[0]):
        relevance = case((DocumentChunk.content.ilike(f"%{terms[0]}%"), 2), else_=0)
    for term in terms[1:]:
        weight = 2 if ascii_pattern.search(term) else 1
        relevance = relevance + case(
            (DocumentChunk.content.ilike(f"%{term}%"), weight), else_=0
        )
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
    return [
        RetrievedChunk(chunk=chunk, document=document, score=None, retrieval_method="keyword")
        for chunk, document, _rel in rows
    ]


def _semantic_search(
    db: Session,
    group_id: str,
    query: str,
    limit: int,
    settings: Settings,
    *,
    allowed_document_ids: set[str] | None = None,
) -> list[RetrievedChunk]:
    if allowed_document_ids is not None and not allowed_document_ids:
        return []
    validate_pgvector_dimension(db, settings)
    client = create_embedding_client(settings)
    query_vector = client.embed_texts([query]).vectors[0]

    from semantic_lighthouse.services.retrieval import _semantic_search_with_vector

    results = _semantic_search_with_vector(
        db,
        group_id,
        query_vector,
        limit,
        allowed_document_ids=allowed_document_ids,
    )
    return [
        RetrievedChunk(chunk=r.chunk, document=r.document, score=r.score, retrieval_method="semantic")
        for r in results
    ]


def _citations(retrieved: list[RetrievedChunk], query: str, max_context_chars: int) -> list[RagCitation]:
    citations: list[RagCitation] = []
    used_chars = 0
    for item in _prioritize_citation_candidates(retrieved):
        frontmatter = item.document.frontmatter or {}
        chunk_snippet = snippet(item.chunk.content, query, radius=240)
        remaining = max_context_chars - used_chars
        if remaining <= 0:
            break
        chunk_snippet = chunk_snippet[:remaining].strip()
        if not chunk_snippet:
            continue
        used_chars += len(chunk_snippet)
        citation = RagCitation(
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
            match_reason=_build_match_reason(query, item.document.title, item.chunk.heading_path, chunk_snippet, item.score, item.retrieval_method),
        )
        citations.append(citation)
    return citations


def _prioritize_citation_candidates(retrieved: list[RetrievedChunk]) -> list[RetrievedChunk]:
    """Prefer diverse source documents before overflowing with repeats.

    Retrieval ranking still decides the order. This pass only prevents one
    long document from occupying every visible citation when other relevant
    documents are available.
    """
    first_pass: list[RetrievedChunk] = []
    overflow: list[RetrievedChunk] = []
    per_document: dict[str, int] = {}

    for item in retrieved:
        if not _usable_citation_candidate(item):
            continue
        document_count = per_document.get(item.document.id, 0)
        if document_count < MAX_CITATIONS_PER_DOCUMENT_FIRST_PASS:
            first_pass.append(item)
            per_document[item.document.id] = document_count + 1
        else:
            overflow.append(item)

    return first_pass + overflow


def _usable_citation_candidate(item: RetrievedChunk) -> bool:
    if not item.chunk.content or not item.chunk.content.strip():
        return False
    return item.score is None or item.score > 0


def _build_match_reason(
    query: str,
    title: str,
    heading_path: str | None,
    snippet_text: str,
    score: float | None,
    retrieval_method: str,
) -> str:
    """Generate a Chinese match reason based on simple keyword / score rules."""
    terms = _keyword_terms(query)
    hit_terms = [t for t in terms if t and len(t) >= 2]

    # rule 1: terms in title
    title_hits = [t for t in hit_terms if t.lower() in title.lower()]
    if title_hits:
        shown = title_hits[:5]
        return f"标题包含「{'、'.join(shown)}」等问题关键词。"

    # rule 2: terms in heading
    heading = heading_path or ""
    heading_hits = [t for t in hit_terms if t.lower() in heading.lower()]
    if heading_hits:
        shown = heading_hits[:5]
        return f"所在章节标题包含「{'、'.join(shown)}」等问题关键词。"

    # rule 3: terms in snippet
    snippet_hits = [t for t in hit_terms if t.lower() in snippet_text.lower()]
    if snippet_hits:
        shown = snippet_hits[:5]
        return f"片段包含「{'、'.join(shown)}」等问题关键词。"

    # rule 4: semantic with high score
    if retrieval_method == "semantic" and score is not None and score >= 0.7:
        return f"语义检索匹配分较高（{score:.2f}），与问题语义高度相关。"

    # rule 5: hybrid with decent score
    if retrieval_method == "hybrid" and score is not None and score >= 0.5:
        return f"混合检索排序靠前（匹配分 {score:.2f}），可能与问题语义相关。"

    # rule 6: keyword retrieval
    if retrieval_method == "keyword":
        return "关键词检索命中，与问题可能存在关键词层面的关联。"

    # rule 7: fallback
    return "与问题可能存在语义关联，建议人工复核引用内容是否支撑回答。"


def _keyword_terms(query: str) -> list[str]:
    raw_terms = re.findall(r"[A-Za-z0-9_-]+|[\u4e00-\u9fff]{2,}", query)
    ascii_terms: list[str] = []
    cjk_terms: list[str] = []
    for term in raw_terms:
        normalized = term.strip()
        if len(normalized) < 2:
            continue
        # Split long Chinese sequences into overlapping bi-grams so ILIKE
        # can match against document content (which won't contain the
        # verbatim question phrasing).
        if re.fullmatch(r"[\u4e00-\u9fff]{3,}", normalized):
            for i in range(len(normalized) - 1):
                bigram = normalized[i : i + 2]
                if bigram not in cjk_terms:
                    cjk_terms.append(bigram)
        elif normalized not in ascii_terms:
            ascii_terms.append(normalized)
    # ASCII terms are more distinctive \u2014 put them first, then CJK bi-grams.
    terms = ascii_terms + cjk_terms
    return terms[:8]
