from __future__ import annotations

import logging
import shutil
from datetime import timedelta
from pathlib import Path
from shutil import copyfileobj

from sqlalchemy import select
from sqlalchemy.orm import Session

from semantic_lighthouse.config import Settings
from semantic_lighthouse.models import Document, DocumentUploadChunk, DocumentUploadSession, as_utc, utc_now
from semantic_lighthouse.services.document_files import hash_bytes

logger = logging.getLogger(__name__)


def safe_file_name(file_name: str) -> str:
    name = Path(file_name or "").name
    if not name:
        raise ValueError("File name is required")
    return name


def storage_root(settings: Settings) -> Path:
    path = Path(settings.document_storage_path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def upload_tmp_root(settings: Settings) -> Path:
    path = Path(settings.upload_tmp_path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def uploaded_chunk_indexes(session: DocumentUploadSession) -> list[int]:
    return sorted(chunk.chunk_index for chunk in session.chunks)


def session_is_expired(session: DocumentUploadSession) -> bool:
    return as_utc(session.expires_at) <= utc_now()


def find_ready_document_by_file_hash(db: Session, group_id: str, file_hash: str) -> Document | None:
    return db.scalar(
        select(Document).where(
            Document.group_id == group_id,
            Document.file_hash == file_hash,
            Document.status == "ready",
        )
    )


def find_active_upload_session(db: Session, group_id: str, file_hash: str) -> DocumentUploadSession | None:
    sessions = db.scalars(
        select(DocumentUploadSession)
        .where(
            DocumentUploadSession.group_id == group_id,
            DocumentUploadSession.file_hash == file_hash,
            DocumentUploadSession.status == "uploading",
        )
        .order_by(DocumentUploadSession.created_at.desc())
    ).all()
    for session in sessions:
        if not session_is_expired(session):
            return session
        session.status = "expired"
    if sessions:
        db.commit()
    return None


def create_upload_session(
    db: Session,
    *,
    group_id: str,
    created_by: str,
    file_name: str,
    file_size: int,
    file_hash: str,
    chunk_size: int,
    expire_hours: int,
) -> DocumentUploadSession:
    total_chunks = (file_size + chunk_size - 1) // chunk_size
    session = DocumentUploadSession(
        group_id=group_id,
        created_by=created_by,
        file_name=file_name,
        file_size=file_size,
        file_hash=file_hash,
        chunk_size=chunk_size,
        total_chunks=total_chunks,
        status="uploading",
        expires_at=utc_now() + timedelta(hours=expire_hours),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def write_upload_chunk(
    db: Session,
    *,
    settings: Settings,
    session: DocumentUploadSession,
    chunk_index: int,
    content: bytes,
) -> DocumentUploadChunk:
    relative_path = Path(session.group_id) / session.id / f"{chunk_index}.part"
    full_path = upload_tmp_root(settings) / relative_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_bytes(content)

    now = utc_now()
    existing = db.scalar(
        select(DocumentUploadChunk).where(
            DocumentUploadChunk.upload_id == session.id,
            DocumentUploadChunk.chunk_index == chunk_index,
        )
    )
    if existing is None:
        chunk = DocumentUploadChunk(
            upload_id=session.id,
            group_id=session.group_id,
            chunk_index=chunk_index,
            chunk_size=len(content),
            chunk_hash=hash_bytes(content),
            storage_path=relative_path.as_posix(),
            created_at=now,
            updated_at=now,
        )
        db.add(chunk)
    else:
        chunk = existing
        chunk.chunk_size = len(content)
        chunk.chunk_hash = hash_bytes(content)
        chunk.storage_path = relative_path.as_posix()
        chunk.updated_at = now
    db.commit()
    db.refresh(chunk)
    return chunk


def merge_upload_chunks(settings: Settings, session: DocumentUploadSession) -> tuple[Path, str]:
    storage_relative = Path(session.group_id) / session.id / safe_file_name(session.file_name)
    storage_path = storage_root(settings) / storage_relative
    storage_path.parent.mkdir(parents=True, exist_ok=True)
    chunks_by_index = {chunk.chunk_index: chunk for chunk in session.chunks}

    with storage_path.open("wb") as output:
        for index in range(session.total_chunks):
            chunk = chunks_by_index[index]
            chunk_path = upload_tmp_root(settings) / chunk.storage_path
            with chunk_path.open("rb") as source:
                copyfileobj(source, output)

    return storage_path, storage_relative.as_posix()


def cleanup_upload_temp_dir(settings: Settings, session: DocumentUploadSession) -> None:
    """Remove all temp chunk ``.part`` files and the session directory.

    Best-effort: a failure here is logged but never raised to the caller
    because the upload outcome (success / hash-fail / parse-fail) has
    already been decided.
    """
    try:
        temp_dir = upload_tmp_root(settings) / session.group_id / session.id
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
    except OSError:
        logger.warning("Failed to clean up upload temp dir: %s", temp_dir, exc_info=True)


def cleanup_merged_file(settings: Settings, storage_path: Path) -> None:
    """Remove a merged file from document-storage after verification or parse failure.

    Also removes empty parent directories up to (but not including) the
    storage root so that failed sessions do not leave empty folder trees.
    """
    try:
        if storage_path.exists():
            storage_path.unlink()
        parent = storage_path.parent
        root = storage_root(settings)
        while parent != root and parent != parent.parent:
            try:
                if parent.exists() and not any(parent.iterdir()):
                    parent.rmdir()
                    parent = parent.parent
                else:
                    break
            except OSError:
                break
    except OSError:
        logger.warning("Failed to clean up merged file: %s", storage_path, exc_info=True)
