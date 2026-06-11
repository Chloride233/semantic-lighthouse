from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from semantic_lighthouse.config import Settings
from semantic_lighthouse.models import (
    Document,
    DocumentChunk,
    IngestionJob,
    utc_now,
)
from semantic_lighthouse.services.document_files import parse_document_bytes
from semantic_lighthouse.services.embeddings import EmbeddingError, create_embedding_client

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EtlChunk:
    chunk_index: int
    heading_path: str | None
    content: str
    content_hash: str


# ── orchestrator ───────────────────────────────────────────────────────────


def run_etl_job(
    db_factory: Any,
    settings: Settings,
    job_id: str,
) -> None:
    """Execute the full ETL pipeline for an ingestion job.

    *db_factory* must be a callable that returns a new :class:`Session`
    (e.g. a ``sessionmaker``).  Each retry attempt opens a fresh session
    so that a previous rollback does not leave the session in an
    inconsistent state.
    """
    max_attempts = settings.ingestion_max_attempts
    last_error: str | None = None

    for attempt in range(1, max_attempts + 1):
        db: Session = db_factory()
        job: IngestionJob | None = None
        document: Document | None = None
        was_ready: bool = False
        try:
            job = db.get(IngestionJob, job_id)
            if job is None:
                logger.error("Ingestion job %s not found", job_id)
                return
            document = db.get(Document, job.document_id)
            if document is None:
                _fail_job(db, job, None, "Document not found")
                return

            was_ready = document.status == "ready"
            job.attempt_count = attempt
            _transition_job(db, job, "running", "extract")
            document.status = "processing"
            db.commit()

            # 1. Extract
            markdown = _extract_markdown(document, settings)

            # 2. Parse (handled within extract for uploaded files)
            _transition_job(db, job, "running", "parse")

            # 3. Clean
            _transition_job(db, job, "running", "clean")
            markdown = clean_markdown(markdown)

            # 4. Chunk
            _transition_job(db, job, "running", "chunk")
            chunks = chunk_structured(markdown, settings)

            # 5. Embedding
            _transition_job(db, job, "running", "embed")
            client = create_embedding_client(settings)
            chunk_texts = [chunk.content for chunk in chunks]
            all_vectors: list[list[float]] = []
            embedding_model = settings.embedding_model
            batch_size = settings.embedding_batch_size
            for start in range(0, len(chunk_texts), batch_size):
                batch_texts = chunk_texts[start : start + batch_size]
                try:
                    result = client.embed_texts(batch_texts)
                except EmbeddingError:
                    raise  # propagate to outer retry loop
                embedding_model = result.model
                all_vectors.extend(result.vectors)

            # 6. Load
            _transition_job(db, job, "running", "load")
            for old_chunk in list(document.chunks):
                db.delete(old_chunk)
            db.flush()

            now = utc_now()
            for chunk, vector in zip(chunks, all_vectors):
                db.add(
                    DocumentChunk(
                        group_id=document.group_id,
                        document_id=document.id,
                        chunk_index=chunk.chunk_index,
                        heading_path=chunk.heading_path,
                        content=chunk.content,
                        content_hash=chunk.content_hash,
                        embedding=vector,
                        embedding_model=embedding_model,
                        embedded_at=now,
                    )
                )

            # 7. Finalize
            document.status = "ready"
            document.ingestion_error = None
            document.processed_at = now
            job.status = "succeeded"
            job.finished_at = now
            job.step_log = {**job.step_log, "finalized_at": now.isoformat()}
            db.commit()
            return  # success — exit the retry loop

        except Exception as exc:
            db.rollback()
            last_error = str(exc)
            if attempt >= max_attempts:
                db.close()
                db = db_factory()
                job = db.get(IngestionJob, job_id)
                document = db.get(Document, job.document_id) if job else None
                if job is not None:
                    if document is not None and was_ready:
                        # Restore ready — old chunks are still searchable.
                        document.status = "ready"
                        document.ingestion_error = None
                        # Only fail the job; document stays ready.
                        job.status = "failed"
                        job.error_message = last_error
                        job.finished_at = utc_now()
                        db.commit()
                    else:
                        _fail_job(db, job, document, last_error)
                return

            # Update job for retry — keep document in a searchable state.
            if job is not None:
                job.status = "pending"
                job.current_step = None
                job.error_message = last_error
                if document is not None and not was_ready:
                    document.status = "uploaded"
                elif document is not None:
                    document.status = "ready"  # was ready, keep searchable
                db.commit()

            backoff = 2 ** (attempt - 1)
            time.sleep(backoff)
        finally:
            db.close()


# ── job state helpers ─────────────────────────────────────────────────────


def _fail_job(db: Session, job: IngestionJob, document: Document | None, error_message: str) -> None:
    job.status = "failed"
    job.error_message = error_message
    job.finished_at = utc_now()
    if document is not None:
        document.status = "failed"
        document.ingestion_error = error_message
    db.commit()


def _transition_job(db: Session, job: IngestionJob, status: str, step: str) -> None:
    job.status = status
    job.current_step = step
    # Explicit dict replacement so SQLAlchemy always detects the change.
    job.step_log = {**job.step_log, step: {"started_at": utc_now().isoformat()}}
    if job.started_at is None:
        job.started_at = utc_now()
    db.commit()


# ── extract ────────────────────────────────────────────────────────────────


def _extract_markdown(document: Document, settings: Settings) -> str:
    if document.original_storage_path:
        root = Path(settings.document_storage_path).resolve()
        candidate = (root / document.original_storage_path).resolve()
        if str(candidate).startswith(str(root)) and candidate.exists():
            content = candidate.read_bytes()
            parsed = parse_document_bytes(content, document.file_name)
            return parsed.markdown
    return document.raw_content


# ── clean ──────────────────────────────────────────────────────────────────


def clean_markdown(text: str) -> str:
    """Basic text cleaning before chunking.

    - Collapse 3+ consecutive newlines into 2
    - Remove control characters (keep ``\\n``, ``\\t``)
    - Remove lines that are only whitespace
    """
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", "", text)
    lines = [line for line in text.splitlines() if line.strip()]
    return "\n".join(lines)


# ── chunking ───────────────────────────────────────────────────────────────


def chunk_structured(markdown: str, settings: Settings) -> list[EtlChunk]:
    """Structure-aware chunking for markdown text.

    1. Split by heading boundaries.
    2. Enforce min/max character limits.
    3. Optionally add overlap (disabled by default at 0).

    Requires ``chunk_target_chars <= chunk_max_chars`` to prevent an
    infinite split-merge loop.
    """
    if settings.chunk_target_chars > settings.chunk_max_chars:
        raise ValueError(
            f"chunk_target_chars ({settings.chunk_target_chars}) must not exceed "
            f"chunk_max_chars ({settings.chunk_max_chars})"
        )
    sections = _split_by_headings(markdown)
    chunks = _control_chunk_sizes(sections, settings)
    chunks = _merge_small_chunks(chunks, settings)
    return chunks


def _split_by_headings(text: str) -> list[tuple[str | None, str]]:
    """Split markdown into (heading_path, section_text) pairs on heading boundaries."""
    if not text.strip():
        return []

    heading_pattern = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
    sections: list[tuple[str | None, str]] = []
    current_heading: str | None = None
    current_lines: list[str] = []
    heading_stack: list[str] = []

    for line in text.splitlines():
        match = heading_pattern.match(line)
        if match:
            if current_lines:
                sections.append((current_heading, "\n".join(current_lines)))
                current_lines = []
            level = len(match.group(1))
            heading_text = match.group(2).strip()
            heading_stack = heading_stack[: max(level - 1, 0)]
            heading_stack.append(heading_text)
            current_heading = " > ".join(part for part in heading_stack if part)
        current_lines.append(line)

    if current_lines:
        sections.append((current_heading, "\n".join(current_lines)))
    if not sections:
        return [(None, text)]
    return sections


def _control_chunk_sizes(
    sections: list[tuple[str | None, str]],
    settings: Settings,
) -> list[EtlChunk]:
    """Split oversized sections by paragraph then sentence; keep normal-sized as-is."""
    chunks: list[EtlChunk] = []
    max_chars = settings.chunk_max_chars

    for heading_path, section_text in sections:
        if len(section_text) <= max_chars:
            chunks.append(
                EtlChunk(
                    chunk_index=len(chunks),
                    heading_path=heading_path,
                    content=section_text.strip(),
                    content_hash=_hash_text(section_text.strip()),
                )
            )
        else:
            sub = _split_section_oversized(section_text, heading_path, max_chars, len(chunks))
            chunks.extend(sub)

    return [
        EtlChunk(chunk_index=i, heading_path=c.heading_path, content=c.content, content_hash=c.content_hash)
        for i, c in enumerate(chunks)
    ]


def _split_section_oversized(
    text: str,
    heading_path: str | None,
    max_chars: int,
    start_index: int,
) -> list[EtlChunk]:
    """Split an oversized section: paragraphs first, then sentences, then hard-split."""
    chunks: list[EtlChunk] = []

    paragraphs = re.split(r"\n\s*\n", text)
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if len(para) <= max_chars:
            chunks.append(
                EtlChunk(
                    chunk_index=start_index + len(chunks),
                    heading_path=heading_path,
                    content=para,
                    content_hash=_hash_text(para),
                )
            )
        else:
            sub = _split_by_sentence(para, heading_path, max_chars, start_index + len(chunks))
            chunks.extend(sub)

    return chunks


def _split_by_sentence(
    text: str,
    heading_path: str | None,
    max_chars: int,
    start_index: int,
) -> list[EtlChunk]:
    """Split text by sentence boundaries; hard-split if a single sentence exceeds max_chars."""
    chunks: list[EtlChunk] = []
    sentences = re.split(r"(?<=[.!?。！？])\s+", text)
    current = ""

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        if len(sentence) > max_chars:
            if current:
                chunks.append(
                    EtlChunk(
                        chunk_index=start_index + len(chunks),
                        heading_path=heading_path,
                        content=current.strip(),
                        content_hash=_hash_text(current.strip()),
                    )
                )
                current = ""
            for i in range(0, len(sentence), max_chars):
                piece = sentence[i : i + max_chars].strip()
                if piece:
                    chunks.append(
                        EtlChunk(
                            chunk_index=start_index + len(chunks),
                            heading_path=heading_path,
                            content=piece,
                            content_hash=_hash_text(piece),
                        )
                    )
        elif current and len(current) + len(sentence) + 1 > max_chars:
            chunks.append(
                EtlChunk(
                    chunk_index=start_index + len(chunks),
                    heading_path=heading_path,
                    content=current.strip(),
                    content_hash=_hash_text(current.strip()),
                )
            )
            current = sentence
        else:
            current = f"{current} {sentence}".strip() if current else sentence

    if current:
        chunks.append(
            EtlChunk(
                chunk_index=start_index + len(chunks),
                heading_path=heading_path,
                content=current.strip(),
                content_hash=_hash_text(current.strip()),
            )
        )

    return chunks


def _merge_small_chunks(chunks: list[EtlChunk], settings: Settings) -> list[EtlChunk]:
    """Merge chunks smaller than min_chars with their neighbor."""
    min_chars = settings.chunk_min_chars
    target_chars = settings.chunk_target_chars

    if len(chunks) <= 1:
        return chunks

    merged: list[EtlChunk] = []
    i = 0
    while i < len(chunks):
        current = chunks[i]
        if len(current.content) < min_chars and i + 1 < len(chunks):
            next_chunk = chunks[i + 1]
            combined = f"{current.content}\n\n{next_chunk.content}"
            merged.append(
                EtlChunk(
                    chunk_index=len(merged),
                    heading_path=_merged_heading(current.heading_path, next_chunk.heading_path),
                    content=combined,
                    content_hash=_hash_text(combined),
                )
            )
            i += 2
        elif len(current.content) < min_chars and merged:
            prev = merged[-1]
            combined = f"{prev.content}\n\n{current.content}"
            merged[-1] = EtlChunk(
                chunk_index=prev.chunk_index,
                heading_path=_merged_heading(prev.heading_path, current.heading_path),
                content=combined,
                content_hash=_hash_text(combined),
            )
            i += 1
        else:
            merged.append(current)
            i += 1

    # Re-check oversized after merging
    result: list[EtlChunk] = []
    for chunk in merged:
        if len(chunk.content) > target_chars:
            sub = _split_section_oversized(chunk.content, chunk.heading_path, target_chars, len(result))
            result.extend(sub)
        else:
            result.append(
                EtlChunk(
                    chunk_index=len(result),
                    heading_path=chunk.heading_path,
                    content=chunk.content,
                    content_hash=chunk.content_hash,
                )
            )

    return result


# ── helpers ────────────────────────────────────────────────────────────────


def _merged_heading(left: str | None, right: str | None) -> str | None:
    """Combine two heading paths when merging chunks so provenance is visible."""
    if left and right:
        return f"{left} | {right}"
    return left or right


def _hash_text(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()
