from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile, status
from pgvector.sqlalchemy import Vector
from sqlalchemy import Float, bindparam, cast, select
from sqlalchemy.orm import Session, selectinload

from semantic_lighthouse.config import Settings, get_settings
from semantic_lighthouse.database import SessionLocal, get_db
from semantic_lighthouse.dependencies import get_current_user, get_membership_or_404, require_group_role
from semantic_lighthouse.models import Document, DocumentChunk, DocumentUploadSession, IngestionJob, User, utc_now
from semantic_lighthouse.schemas import (
    DocumentChunkResponse,
    DocumentDetailResponse,
    DocumentResponse,
    DocumentSearchResult,
    EmbeddingRebuildResponse,
    IngestionJobDetailResponse,
    IngestionJobResponse,
    LocalImportResponse,
    SemanticSearchResult,
    UploadChunkResponse,
    UploadInitRequest,
    UploadInitResponse,
    UploadSessionResponse,
)
from semantic_lighthouse.services.document_files import (
    DocumentParseError,
    hash_bytes,
    parse_document_bytes,
    supported_document_extension,
    verify_file_hash,
)
from semantic_lighthouse.services.document_etl import run_etl_job
from semantic_lighthouse.services.document_ingestion import ingest_markdown, parse_markdown, should_import_markdown
from semantic_lighthouse.services.document_uploads import (
    cleanup_merged_file,
    cleanup_upload_temp_dir,
    create_upload_session,
    find_active_upload_session,
    find_ready_document_by_file_hash,
    merge_upload_chunks,
    safe_file_name,
    session_is_expired,
    uploaded_chunk_indexes,
    write_upload_chunk,
)
from semantic_lighthouse.services.embeddings import EmbeddingError, cosine_similarity, create_embedding_client

from ._shared import PGVECTOR_DIMENSION, snippet, validate_pgvector_dimension

router = APIRouter(prefix="/groups/{group_id}/documents", tags=["documents"])


def _document_response(document: Document) -> DocumentResponse:
    return DocumentResponse(
        id=document.id,
        group_id=document.group_id,
        title=document.title,
        file_name=document.file_name,
        source_path=document.source_path,
        content_hash=document.content_hash,
        file_hash=document.file_hash,
        mime_type=document.mime_type,
        file_size=document.file_size,
        original_storage_path=document.original_storage_path,
        parser=document.parser,
        frontmatter=document.frontmatter,
        status=document.status,
        ingestion_error=document.ingestion_error,
        processed_at=document.processed_at,
        created_by=document.created_by,
        created_at=document.created_at,
    )


def _chunk_response(chunk: DocumentChunk) -> DocumentChunkResponse:
    return DocumentChunkResponse(
        id=chunk.id,
        document_id=chunk.document_id,
        group_id=chunk.group_id,
        chunk_index=chunk.chunk_index,
        heading_path=chunk.heading_path,
        content=chunk.content,
        content_hash=chunk.content_hash,
    )


@router.post("/import-local", response_model=LocalImportResponse, status_code=status.HTTP_201_CREATED)
def import_local_knowledge_base(
    group_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> LocalImportResponse:
    require_group_role(db, current_user.id, group_id, {"owner", "admin"})
    knowledge_base_path = Path(settings.knowledge_base_path)
    if not knowledge_base_path.exists() or not knowledge_base_path.is_dir():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge base path not found")

    imported: list[Document] = []
    skipped_count = 0
    for path in sorted(knowledge_base_path.rglob("*.md")):
        if not should_import_markdown(path):
            skipped_count += 1
            continue
        markdown = path.read_text(encoding="utf-8")
        relative_path = path.relative_to(knowledge_base_path).as_posix()
        result = ingest_markdown(
            db,
            group_id=group_id,
            created_by=current_user.id,
            file_name=path.name,
            source_path=relative_path,
            markdown=markdown,
        )
        if result.created:
            imported.append(result.document)
        else:
            skipped_count += 1

    return LocalImportResponse(
        imported_count=len(imported),
        skipped_count=skipped_count,
        documents=[_document_response(document) for document in imported],
    )


@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    group_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> DocumentResponse:
    require_group_role(db, current_user.id, group_id, {"owner", "admin"})
    try:
        file_name = safe_file_name(file.filename or "")
        supported_document_extension(file_name)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except DocumentParseError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    content = await file.read()
    if len(content) > settings.max_markdown_upload_bytes:
        raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail="Uploaded file is too large")
    try:
        parsed = parse_document_bytes(content, file_name)
    except DocumentParseError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    result = ingest_markdown(
        db,
        group_id=group_id,
        created_by=current_user.id,
        file_name=file_name,
        source_path=f"upload:{file_name}",
        markdown=parsed.markdown,
        file_hash=hash_bytes(content),
        mime_type=parsed.mime_type,
        file_size=len(content),
        parser=parsed.parser,
    )
    return _document_response(result.document)


@router.post("/uploads/init", response_model=UploadInitResponse, status_code=status.HTTP_201_CREATED)
def init_document_upload(
    group_id: str,
    request: UploadInitRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> UploadInitResponse:
    require_group_role(db, current_user.id, group_id, {"owner", "admin"})
    try:
        file_name = safe_file_name(request.file_name)
        supported_document_extension(file_name)
    except (ValueError, DocumentParseError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    file_hash = request.file_hash.lower()
    if request.file_size > settings.max_document_upload_bytes:
        raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail="Uploaded file is too large")

    existing = find_ready_document_by_file_hash(db, group_id, file_hash)
    if existing is not None:
        return UploadInitResponse(type="INSTANT", document_id=existing.id)

    active_session = find_active_upload_session(db, group_id, file_hash)
    if active_session is not None:
        return _upload_init_session_response(active_session)

    chunk_size = request.chunk_size or settings.upload_chunk_bytes
    if chunk_size <= 0 or chunk_size > settings.max_document_upload_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid chunk size")
    upload_session = create_upload_session(
        db,
        group_id=group_id,
        created_by=current_user.id,
        file_name=file_name,
        file_size=request.file_size,
        file_hash=file_hash,
        chunk_size=chunk_size,
        expire_hours=settings.upload_session_expire_hours,
    )
    return _upload_init_session_response(upload_session)


@router.put("/uploads/{upload_id}/chunks/{chunk_index}", response_model=UploadChunkResponse)
async def upload_document_chunk(
    group_id: str,
    upload_id: str,
    chunk_index: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> UploadChunkResponse:
    require_group_role(db, current_user.id, group_id, {"owner", "admin"})
    upload_session = _get_upload_session_or_404(db, group_id, upload_id)
    _ensure_uploading_session(db, upload_session, settings)
    if chunk_index < 0 or chunk_index >= upload_session.total_chunks:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid chunk index")

    content = await file.read()
    expected_max = upload_session.chunk_size
    if chunk_index < upload_session.total_chunks - 1 and len(content) != expected_max:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Chunk size does not match session")
    if chunk_index == upload_session.total_chunks - 1 and len(content) > expected_max:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Chunk size does not match session")
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Chunk cannot be empty")

    write_upload_chunk(db, settings=settings, session=upload_session, chunk_index=chunk_index, content=content)
    db.refresh(upload_session)
    uploaded_chunks = uploaded_chunk_indexes(upload_session)
    return UploadChunkResponse(
        upload_id=upload_session.id,
        uploaded_count=len(uploaded_chunks),
        total_count=upload_session.total_chunks,
        uploaded_chunks=uploaded_chunks,
    )


@router.get("/uploads/{upload_id}", response_model=UploadSessionResponse)
def get_document_upload_session(
    group_id: str,
    upload_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UploadSessionResponse:
    require_group_role(db, current_user.id, group_id, {"owner", "admin"})
    upload_session = _get_upload_session_or_404(db, group_id, upload_id)
    return _upload_session_response(upload_session)


@router.post("/uploads/{upload_id}/complete", response_model=DocumentResponse)
def complete_document_upload(
    group_id: str,
    upload_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> DocumentResponse:
    require_group_role(db, current_user.id, group_id, {"owner", "admin"})
    upload_session = _get_upload_session_or_404(db, group_id, upload_id)
    if upload_session.status == "completed":
        existing = find_ready_document_by_file_hash(db, group_id, upload_session.file_hash)
        if existing is None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Completed upload has no document")
        return _document_response(existing)
    _ensure_uploading_session(db, upload_session, settings)

    uploaded_chunks = uploaded_chunk_indexes(upload_session)
    if uploaded_chunks != list(range(upload_session.total_chunks)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Upload chunks are incomplete")

    upload_session.status = "completing"
    db.commit()

    storage_path, relative_storage_path = merge_upload_chunks(settings, upload_session)

    if not verify_file_hash(storage_path, upload_session.file_hash, upload_session.file_size):
        cleanup_merged_file(settings, storage_path)
        cleanup_upload_temp_dir(settings, upload_session)
        upload_session.status = "failed"
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file hash mismatch")

    content = storage_path.read_bytes()

    try:
        parsed = parse_document_bytes(content, upload_session.file_name)
    except DocumentParseError as exc:
        cleanup_merged_file(settings, storage_path)
        cleanup_upload_temp_dir(settings, upload_session)
        upload_session.status = "failed"
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    # Create document as "uploaded" — ingestion runs async via background task.
    doc_content_hash = hash_bytes(content)
    existing = db.scalar(
        select(Document).where(
            Document.group_id == group_id,
            Document.content_hash == doc_content_hash,
        )
    )
    if existing is not None:
        cleanup_upload_temp_dir(settings, upload_session)
        upload_session.status = "completed"
        upload_session.completed_at = utc_now()
        db.commit()
        return _document_response(existing)

    parsed_md = parse_markdown(parsed.markdown, upload_session.file_name)
    document = Document(
        group_id=group_id,
        title=parsed_md.title,
        file_name=upload_session.file_name,
        source_path=f"upload:{upload_session.file_name}",
        content_hash=doc_content_hash,
        file_hash=upload_session.file_hash,
        mime_type=parsed.mime_type,
        file_size=upload_session.file_size,
        original_storage_path=relative_storage_path,
        parser=parsed.parser,
        frontmatter=parsed_md.frontmatter,
        raw_content=parsed.markdown,
        status="uploaded",
        created_by=current_user.id,
    )
    db.add(document)
    db.flush()

    job = IngestionJob(
        group_id=group_id,
        document_id=document.id,
        upload_session_id=upload_session.id,
        status="pending",
        attempt_count=1,
        max_attempts=settings.ingestion_max_attempts,
        step_log={},
        created_by=current_user.id,
    )
    db.add(job)
    db.flush()

    cleanup_upload_temp_dir(settings, upload_session)
    upload_session.status = "completed"
    upload_session.completed_at = utc_now()
    db.commit()

    # Trigger async ETL after the response is sent.
    background_tasks.add_task(run_etl_job, SessionLocal, settings, job.id)

    return _document_response(document)


# ── ingestion job endpoints ─────────────────────────────────────────────


@router.post("/{document_id}/ingestion-jobs", response_model=IngestionJobResponse, status_code=status.HTTP_201_CREATED)
def create_ingestion_job(
    group_id: str,
    document_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> IngestionJobResponse:
    require_group_role(db, current_user.id, group_id, {"owner", "admin"})
    document = db.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.group_id == group_id,
        )
    )
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    if document.status == "processing":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Document ingestion is already in progress")

    # Never downgrade a ready document — old chunks must remain searchable.
    was_ready = document.status == "ready"
    if not was_ready:
        document.status = "uploaded"
    job = IngestionJob(
        group_id=group_id,
        document_id=document.id,
        status="pending",
        attempt_count=1,
        max_attempts=settings.ingestion_max_attempts,
        step_log={},
        created_by=current_user.id,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    background_tasks.add_task(run_etl_job, SessionLocal, settings, job.id)
    return _ingestion_job_response(job)


@router.get("/{document_id}/ingestion-jobs", response_model=list[IngestionJobResponse])
def list_ingestion_jobs(
    group_id: str,
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[IngestionJobResponse]:
    get_membership_or_404(db, current_user.id, group_id)
    document = db.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.group_id == group_id,
        )
    )
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    jobs = db.scalars(
        select(IngestionJob)
        .where(IngestionJob.document_id == document_id, IngestionJob.group_id == group_id)
        .order_by(IngestionJob.created_at.desc())
    ).all()
    return [_ingestion_job_response(job) for job in jobs]


@router.get("/ingestion-jobs/{job_id}", response_model=IngestionJobDetailResponse)
def get_ingestion_job(
    group_id: str,
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> IngestionJobDetailResponse:
    get_membership_or_404(db, current_user.id, group_id)
    job = db.scalar(
        select(IngestionJob).where(
            IngestionJob.id == job_id,
            IngestionJob.group_id == group_id,
        )
    )
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ingestion job not found")
    return _ingestion_job_detail_response(job)


# ── document list / search ─────────────────────────────────────────────


@router.get("", response_model=list[DocumentResponse])
def list_documents(
    group_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[DocumentResponse]:
    get_membership_or_404(db, current_user.id, group_id)
    documents = db.scalars(
        select(Document).where(Document.group_id == group_id).order_by(Document.created_at.desc())
    ).all()
    return [_document_response(document) for document in documents]


@router.get("/search", response_model=list[DocumentSearchResult])
def search_documents(
    group_id: str,
    q: str = Query(min_length=1, max_length=200),
    limit: int = Query(default=10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[DocumentSearchResult]:
    get_membership_or_404(db, current_user.id, group_id)
    rows = db.execute(
        select(DocumentChunk, Document)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(
            DocumentChunk.group_id == group_id,
            Document.group_id == group_id,
            Document.status == "ready",
            DocumentChunk.content.ilike(f"%{q}%"),
        )
        .order_by(Document.created_at.desc(), DocumentChunk.chunk_index.asc())
        .limit(limit)
    ).all()
    return [_search_result(chunk, document, q) for chunk, document in rows]


@router.post("/embeddings/rebuild", response_model=EmbeddingRebuildResponse)
def rebuild_document_embeddings(
    group_id: str,
    force: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> EmbeddingRebuildResponse:
    require_group_role(db, current_user.id, group_id, {"owner", "admin"})
    validate_pgvector_dimension(db, settings)
    chunks = db.scalars(
        select(DocumentChunk)
        .where(DocumentChunk.group_id == group_id)
        .order_by(DocumentChunk.document_id.asc(), DocumentChunk.chunk_index.asc())
    ).all()
    pending = [chunk for chunk in chunks if force or chunk.embedding is None]
    skipped_count = len(chunks) - len(pending)
    client = create_embedding_client(settings)
    processed_count = 0
    failed_count = 0
    embedding_model = settings.embedding_model

    for start in range(0, len(pending), settings.embedding_batch_size):
        batch = pending[start : start + settings.embedding_batch_size]
        try:
            result = client.embed_texts([chunk.content for chunk in batch])
        except EmbeddingError as exc:
            db.rollback()
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
        embedding_model = result.model
        for chunk, vector in zip(batch, result.vectors):
            chunk.embedding = vector
            chunk.embedding_model = result.model
            chunk.embedded_at = utc_now()
            processed_count += 1

    db.commit()
    return EmbeddingRebuildResponse(
        processed_count=processed_count,
        skipped_count=skipped_count,
        failed_count=failed_count,
        embedding_model=embedding_model,
    )


@router.get("/semantic-search", response_model=list[SemanticSearchResult])
def semantic_search_documents(
    group_id: str,
    q: str = Query(min_length=1, max_length=200),
    limit: int = Query(default=10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> list[SemanticSearchResult]:
    get_membership_or_404(db, current_user.id, group_id)
    validate_pgvector_dimension(db, settings)
    client = create_embedding_client(settings)
    try:
        query_vector = client.embed_texts([q]).vectors[0]
    except EmbeddingError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    if db.bind is not None and db.bind.dialect.name == "postgresql":
        return _semantic_search_postgres(db, group_id, query_vector, q, limit)
    return _semantic_search_python(db, group_id, query_vector, q, limit)


@router.get("/{document_id}", response_model=DocumentDetailResponse)
def get_document(
    group_id: str,
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocumentDetailResponse:
    get_membership_or_404(db, current_user.id, group_id)
    document = db.scalar(
        select(Document)
        .options(selectinload(Document.chunks))
        .where(
            Document.id == document_id,
            Document.group_id == group_id,
        )
    )
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    chunks = sorted(document.chunks, key=lambda chunk: chunk.chunk_index)
    return DocumentDetailResponse(
        **_document_response(document).model_dump(),
        chunks=[_chunk_response(chunk) for chunk in chunks],
    )


def _get_upload_session_or_404(db: Session, group_id: str, upload_id: str) -> DocumentUploadSession:
    upload_session = db.scalar(
        select(DocumentUploadSession)
        .options(selectinload(DocumentUploadSession.chunks))
        .where(
            DocumentUploadSession.id == upload_id,
            DocumentUploadSession.group_id == group_id,
        )
    )
    if upload_session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upload session not found")
    return upload_session


def _ensure_uploading_session(
    db: Session, upload_session: DocumentUploadSession, settings: Settings
) -> None:
    if upload_session.status != "uploading":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Upload session is not active")
    if session_is_expired(upload_session):
        upload_session.status = "expired"
        db.commit()
        cleanup_upload_temp_dir(settings, upload_session)
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Upload session expired")


def _upload_init_session_response(upload_session: DocumentUploadSession) -> UploadInitResponse:
    return UploadInitResponse(
        type="UPLOAD_SESSION",
        upload_id=upload_session.id,
        chunk_size=upload_session.chunk_size,
        total_chunks=upload_session.total_chunks,
        uploaded_chunks=uploaded_chunk_indexes(upload_session),
        expires_at=upload_session.expires_at,
    )


def _upload_session_response(upload_session: DocumentUploadSession) -> UploadSessionResponse:
    uploaded_chunks = uploaded_chunk_indexes(upload_session)
    return UploadSessionResponse(
        upload_id=upload_session.id,
        group_id=upload_session.group_id,
        file_name=upload_session.file_name,
        file_size=upload_session.file_size,
        file_hash=upload_session.file_hash,
        chunk_size=upload_session.chunk_size,
        total_chunks=upload_session.total_chunks,
        uploaded_chunks=uploaded_chunks,
        uploaded_count=len(uploaded_chunks),
        status=upload_session.status,
        expires_at=upload_session.expires_at,
    )


def _search_result(chunk: DocumentChunk, document: Document, query: str) -> DocumentSearchResult:
    frontmatter = document.frontmatter or {}
    return DocumentSearchResult(
        document_id=document.id,
        chunk_id=chunk.id,
        title=document.title,
        source_path=document.source_path,
        file_name=document.file_name,
        chunk_index=chunk.chunk_index,
        heading_path=chunk.heading_path,
        snippet=snippet(chunk.content, query),
        entity_type=frontmatter.get("entityType"),
        document_type=frontmatter.get("documentType"),
        source=frontmatter.get("source"),
        status=frontmatter.get("status"),
    )


def _semantic_result(
    chunk: DocumentChunk,
    document: Document,
    query: str,
    score: float,
) -> SemanticSearchResult:
    return SemanticSearchResult(
        **_search_result(chunk, document, query).model_dump(),
        score=score,
    )


def _semantic_search_python(
    db: Session,
    group_id: str,
    query_vector: list[float],
    query: str,
    limit: int,
) -> list[SemanticSearchResult]:
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
    return [_semantic_result(chunk, document, query, score) for score, chunk, document in scored[:limit]]


def _semantic_search_postgres(
    db: Session,
    group_id: str,
    query_vector: list[float],
    query: str,
    limit: int,
) -> list[SemanticSearchResult]:
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
        _semantic_result(chunk, document, query, 1.0 - float(distance))
        for chunk, document, distance in rows
    ]


def _ingestion_job_response(job: IngestionJob) -> IngestionJobResponse:
    return IngestionJobResponse(
        id=job.id,
        group_id=job.group_id,
        document_id=job.document_id,
        upload_session_id=job.upload_session_id,
        status=job.status,
        current_step=job.current_step,
        attempt_count=job.attempt_count,
        max_attempts=job.max_attempts,
        error_message=job.error_message,
        created_by=job.created_by,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
    )


def _ingestion_job_detail_response(job: IngestionJob) -> IngestionJobDetailResponse:
    return IngestionJobDetailResponse(
        id=job.id,
        group_id=job.group_id,
        document_id=job.document_id,
        upload_session_id=job.upload_session_id,
        status=job.status,
        current_step=job.current_step,
        attempt_count=job.attempt_count,
        max_attempts=job.max_attempts,
        error_message=job.error_message,
        created_by=job.created_by,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        step_log=job.step_log,
    )
