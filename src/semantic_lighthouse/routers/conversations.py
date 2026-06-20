from __future__ import annotations

from dataclasses import dataclass
import re

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from semantic_lighthouse.config import Settings, get_settings
from semantic_lighthouse.database import get_db
from semantic_lighthouse.dependencies import get_current_user, get_membership_or_404
from semantic_lighthouse.models import BusinessProject, Conversation, ConversationMessage, Document, DocumentChunk, User
from semantic_lighthouse.routers._shared import snippet, validate_pgvector_dimension
from semantic_lighthouse.routers.rag import _build_match_reason
from semantic_lighthouse.schemas import (
    ConversationCreateRequest,
    ConversationDetailResponse,
    ConversationMessageRequest,
    ConversationMessageResponse,
    ConversationResponse,
    RagCitation,
)
from semantic_lighthouse.services.chat import (
    ChatError,
    adjusted_confidence,
    create_chat_client,
    sanitize_references,
)
from semantic_lighthouse.services.embeddings import EmbeddingError, create_embedding_client
from semantic_lighthouse.services.retrieval import ScoredChunk, hybrid_search, _semantic_search_with_vector

router = APIRouter(prefix="/groups/{group_id}/conversations", tags=["conversations"])

HISTORY_ROUNDS = 10

AVAILABLE_TOOLS: list[dict] = [
    {
        "name": "search_knowledge_base",
        "description": (
            "Search the group's knowledge base with a new query string. "
            "Use this when the initial retrieval did not return enough relevant "
            "evidence, or when you need to look up a different angle of the question."
        ),
        "parameters": {
            "query": {
                "type": "string",
                "description": "The search query to execute against the knowledge base",
            },
        },
    },
]

_TOOL_RESULT_MAX_CHARS = 2000


def _execute_tool(
    name: str,
    arguments: dict[str, str],
    db: Session,
    group_id: str,
    settings: Settings,
) -> str:
    """Execute a tool server-side and return a text result for the LLM.

    Only tools in AVAILABLE_TOOLS are allowed.  All searches inherit the
    caller's group_id permission boundary.
    """
    allowed = {t["name"] for t in AVAILABLE_TOOLS}
    if name not in allowed:
        return f"Error: unknown tool '{name}'. Allowed tools: {', '.join(sorted(allowed))}."

    if name == "search_knowledge_base":
        query = arguments.get("query", "")
        if not query.strip():
            return "Error: search_knowledge_base requires a non-empty 'query' parameter."
        results = _keyword_search(db, group_id, query, limit=5)
        if not results:
            return "No matching documents found for the given query."
        lines: list[str] = []
        for i, item in enumerate(results, start=1):
            title = item.document.title
            snippet_text = snippet(item.chunk.content, query, radius=160)
            lines.append(f"[{i}] {title}: {snippet_text}")
        result = "\n".join(lines)
        if len(result) > _TOOL_RESULT_MAX_CHARS:
            result = result[:_TOOL_RESULT_MAX_CHARS].rsplit("\n", 1)[0] + "\n(truncated)"
        return result

    return f"Error: tool '{name}' is registered but has no handler."


@dataclass(frozen=True)
class _ResolvedAnswer:
    text: str
    confidence: str
    knowledge_gaps: list[str]
    model: str


def _resolve_tool_answer(
    client,
    question: str,
    citations: list,
    history: list[dict[str, str]],
    *,
    db: Session,
    group_id: str,
    conversation_id: str,
    settings: Settings,
) -> _ResolvedAnswer:
    """Call LLM, execute tool if requested, return resolved answer fields."""
    response = client.generate_response(
        question, citations, history=history, tools=AVAILABLE_TOOLS,
    )

    if response.is_tool_call:
        tool = response.tool_call
        tool_result = _execute_tool(tool.name, tool.arguments, db, group_id, settings)
        db.add(
            ConversationMessage(
                conversation_id=conversation_id,
                role="tool",
                content=f"Tool: {tool.name}\nResult:\n{tool_result}",
                citations=[],
                knowledge_gaps=[],
                tool_calls=[{"name": tool.name, "arguments": tool.arguments}],
            )
        )
        # Use "user" role for tool results — OpenAI-compatible APIs require
        # tool_call_id on "tool" role messages, which we don't have since
        # tool calling is implemented via JSON-in-content, not native function calling.
        extended_history = history + [
            {"role": "assistant", "content": f"[请求工具: {tool.name}]"},
            {"role": "user", "content": f"[工具结果] {tool_result}"},
        ]
        response = client.generate_response(
            question, citations, history=extended_history, tools=[],
        )

    final_answer = response.answer
    if final_answer is None:
        return _ResolvedAnswer(
            text="Tool execution completed but no final answer was produced.",
            confidence="low",
            knowledge_gaps=["Tool loop did not produce a final answer."],
            model=settings.chat_model,
        )
    final_conf, _ = adjusted_confidence(final_answer.confidence, citations)
    return _ResolvedAnswer(
        text=sanitize_references(final_answer.answer, citations),
        confidence=final_conf,
        knowledge_gaps=final_answer.knowledge_gaps,
        model=final_answer.model,
    )


def _get_project_or_404(db: Session, group_id: str, project_id: str) -> BusinessProject:
    project = db.get(BusinessProject, project_id)
    if project is None or project.group_id != group_id:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _conversation_response(conv: Conversation) -> ConversationResponse:
    return ConversationResponse(
        id=conv.id,
        group_id=conv.group_id,
        user_id=conv.user_id,
        project_id=conv.project_id,
        title=conv.title,
        message_count=len(conv.messages) if conv.messages else 0,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
    )


def _message_response(msg: ConversationMessage) -> ConversationMessageResponse:
    return ConversationMessageResponse(
        id=msg.id,
        conversation_id=msg.conversation_id,
        role=msg.role,
        content=msg.content,
        citations=[RagCitation.model_validate(c) for c in msg.citations] if msg.citations else [],
        retrieval_method=msg.retrieval_method,
        model=msg.model,
        confidence=msg.confidence,
        knowledge_gaps=msg.knowledge_gaps or [],
        tool_calls=msg.tool_calls,
        created_at=msg.created_at,
    )


@router.post("", response_model=ConversationResponse, status_code=201)
def create_conversation(
    group_id: str,
    body: ConversationCreateRequest = ConversationCreateRequest(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConversationResponse:
    get_membership_or_404(db, current_user.id, group_id)
    if body.project_id is not None:
        project = _get_project_or_404(db, group_id, body.project_id)
        if project.status == "archived":
            raise HTTPException(
                status_code=409,
                detail="Cannot create scoped resource in archived project",
            )
    title = (body.title or "New Conversation").strip()[:240] or "New Conversation"
    conv = Conversation(
        group_id=group_id,
        user_id=current_user.id,
        project_id=body.project_id,
        title=title,
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return _conversation_response(conv)


@router.get("", response_model=list[ConversationResponse])
def list_conversations(
    group_id: str,
    project_id: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ConversationResponse]:
    get_membership_or_404(db, current_user.id, group_id)
    conditions = [Conversation.group_id == group_id, Conversation.user_id == current_user.id]
    if project_id is not None:
        _get_project_or_404(db, group_id, project_id)
        conditions.append(Conversation.project_id == project_id)
    convs = db.scalars(
        select(Conversation)
        .where(*conditions)
        .order_by(Conversation.updated_at.desc())
    ).all()
    return [_conversation_response(c) for c in convs]


@router.get("/{conversation_id}", response_model=ConversationDetailResponse)
def get_conversation(
    group_id: str,
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConversationDetailResponse:
    get_membership_or_404(db, current_user.id, group_id)
    conv = db.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.group_id == group_id,
        )
    )
    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    if conv.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot access another user's conversation",
        )
    messages = db.scalars(
        select(ConversationMessage)
        .where(ConversationMessage.conversation_id == conversation_id)
        .order_by(ConversationMessage.created_at.asc())
    ).all()
    detail = ConversationDetailResponse(
        id=conv.id,
        group_id=conv.group_id,
        user_id=conv.user_id,
        project_id=conv.project_id,
        title=conv.title,
        message_count=len(messages),
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        messages=[_message_response(m) for m in messages],
    )
    return detail


@router.post("/{conversation_id}/messages", response_model=ConversationMessageResponse)
def send_message(
    group_id: str,
    conversation_id: str,
    request: ConversationMessageRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ConversationMessageResponse:
    get_membership_or_404(db, current_user.id, group_id)
    conv = db.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.group_id == group_id,
        )
    )
    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    if conv.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot send messages to another user's conversation",
        )
    if conv.project_id:
        project = db.get(BusinessProject, conv.project_id)
        if project is not None and project.status == "archived":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot send messages in a conversation scoped to an archived project",
            )

    # ── load history before adding current user message ───────────────
    history_messages = db.scalars(
        select(ConversationMessage)
        .where(ConversationMessage.conversation_id == conversation_id)
        .order_by(ConversationMessage.created_at.asc())
    ).all()
    history = [
        {"role": m.role, "content": m.content}
        for m in history_messages[-HISTORY_ROUNDS * 2 :]
        if m.role != "tool"  # tool messages lack tool_call_id; OpenAI-compatible APIs reject them
    ]

    # ── persist user message ──────────────────────────────────────────
    user_msg = ConversationMessage(
        conversation_id=conversation_id,
        role="user",
        content=request.question,
        citations=[],
        knowledge_gaps=[],
    )
    db.add(user_msg)

    # ── retrieve ──────────────────────────────────────────────────────
    limit = request.limit or settings.rag_top_k
    retrieval_method = request.retrieval_method
    retrieved = _retrieve(db, group_id, request.question, retrieval_method, limit, settings)

    citations = _build_citations(retrieved, request.question, settings.rag_max_context_chars, retrieval_method)

    if not citations:
        assistant_msg = ConversationMessage(
            conversation_id=conversation_id,
            role="assistant",
            content="The knowledge base did not return enough evidence to generate a reliable consulting answer.",
            citations=[],
            retrieval_method=retrieval_method,
            model="local-evidence-gate",
            confidence="low",
            knowledge_gaps=["No retrieved document chunk supports this question."],
        )
        db.add(assistant_msg)
        conv.updated_at = Conversation.updated_at.type.python_type.now()
        db.commit()
        db.refresh(assistant_msg)
        return _message_response(assistant_msg)

    # ── call LLM with tools, handle tool loop ──────────────────────────
    client = create_chat_client(settings)
    try:
        resolved = _resolve_tool_answer(
            client, request.question, citations, history,
            db=db, group_id=group_id, conversation_id=conversation_id, settings=settings,
        )
    except ChatError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    # ── persist assistant message ─────────────────────────────────────
    assistant_msg = ConversationMessage(
        conversation_id=conversation_id,
        role="assistant",
        content=resolved.text,
        citations=[c.model_dump() for c in citations],
        retrieval_method=retrieval_method,
        model=resolved.model,
        confidence=resolved.confidence,
        knowledge_gaps=resolved.knowledge_gaps,
    )
    db.add(assistant_msg)
    conv.updated_at = Conversation.updated_at.type.python_type.now()
    db.commit()
    db.refresh(assistant_msg)
    return _message_response(assistant_msg)


# ── retrieval helpers (same logic as rag.py, scoped here) ─────────────


def _retrieve(
    db: Session,
    group_id: str,
    question: str,
    retrieval_method: str,
    limit: int,
    settings: Settings,
) -> list[ScoredChunk]:
    if retrieval_method == "keyword":
        return _keyword_search(db, group_id, question, limit)
    if retrieval_method == "semantic":
        try:
            return _semantic_search(db, group_id, question, limit, settings)
        except EmbeddingError as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    if retrieval_method == "hybrid":
        return hybrid_search(db, group_id, question, limit, keyword_weight=0.3, settings=settings)
    # auto: semantic first, fall back to keyword
    try:
        semantic_results = _semantic_search(db, group_id, question, limit, settings)
    except EmbeddingError:
        semantic_results = []
    if semantic_results:
        return semantic_results
    return _keyword_search(db, group_id, question, limit)


def _keyword_search(db: Session, group_id: str, query: str, limit: int) -> list[ScoredChunk]:
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
        ScoredChunk(chunk=chunk, document=document, score=0.0, retrieval_method="keyword")
        for chunk, document in rows
    ]


def _semantic_search(
    db: Session,
    group_id: str,
    query: str,
    limit: int,
    settings: Settings,
) -> list[ScoredChunk]:
    validate_pgvector_dimension(db, settings)
    client = create_embedding_client(settings)
    query_vector = client.embed_texts([query]).vectors[0]
    return _semantic_search_with_vector(db, group_id, query_vector, limit)


def _build_citations(
    retrieved: list[ScoredChunk],
    query: str,
    max_context_chars: int,
    retrieval_method: str,
) -> list[RagCitation]:
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
                retrieval_method=retrieval_method,
                match_reason=_build_match_reason(
                    query, item.document.title, item.chunk.heading_path,
                    chunk_snippet, item.score, retrieval_method,
                ),
            )
        )
    return citations


def _keyword_terms(query: str) -> list[str]:
    raw_terms = re.findall(r"[A-Za-z0-9_-]+|[一-鿿]{2,}", query)
    terms: list[str] = []
    for term in raw_terms:
        normalized = term.strip()
        if len(normalized) < 2:
            continue
        if normalized not in terms:
            terms.append(normalized)
    return terms[:8]
