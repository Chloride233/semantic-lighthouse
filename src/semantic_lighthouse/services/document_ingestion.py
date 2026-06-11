from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from semantic_lighthouse.models import Document, DocumentChunk

SYSTEM_MARKDOWN_FILES = {"INDEX.md", "AUTO_INDEX.md", "schema.md"}


@dataclass(frozen=True)
class ParsedChunk:
    chunk_index: int
    heading_path: str | None
    content: str
    content_hash: str


@dataclass(frozen=True)
class ParsedMarkdown:
    title: str
    frontmatter: dict[str, Any]
    body: str
    content_hash: str
    chunks: list[ParsedChunk]


@dataclass(frozen=True)
class IngestResult:
    document: Document
    created: bool


def should_import_markdown(path: Path) -> bool:
    if path.suffix.lower() != ".md":
        return False
    if path.name in SYSTEM_MARKDOWN_FILES or path.name == "_TEMPLATE.md":
        return False
    return True


def parse_markdown(markdown: str, file_name: str) -> ParsedMarkdown:
    frontmatter, body = _split_frontmatter(markdown)
    title = _extract_title(frontmatter, body, file_name)
    content_hash = hash_text(markdown)
    chunks = _chunk_markdown(body)
    return ParsedMarkdown(
        title=title,
        frontmatter=frontmatter,
        body=body,
        content_hash=content_hash,
        chunks=chunks,
    )


def ingest_markdown(
    db: Session,
    *,
    group_id: str,
    created_by: str,
    file_name: str,
    source_path: str,
    markdown: str,
    file_hash: str | None = None,
    mime_type: str | None = None,
    file_size: int | None = None,
    original_storage_path: str | None = None,
    parser: str | None = None,
) -> IngestResult:
    parsed = parse_markdown(markdown, file_name)
    existing = db.scalar(
        select(Document).where(
            Document.group_id == group_id,
            Document.content_hash == parsed.content_hash,
        )
    )
    if existing is not None:
        return IngestResult(document=existing, created=False)

    document = Document(
        group_id=group_id,
        title=parsed.title,
        file_name=file_name,
        source_path=source_path,
        content_hash=parsed.content_hash,
        file_hash=file_hash or parsed.content_hash,
        mime_type=mime_type or "text/markdown",
        file_size=file_size,
        original_storage_path=original_storage_path,
        parser=parser or "markdown",
        frontmatter=parsed.frontmatter,
        raw_content=markdown,
        status="ready",
        created_by=created_by,
    )
    db.add(document)
    db.flush()
    for chunk in parsed.chunks:
        db.add(
            DocumentChunk(
                group_id=group_id,
                document_id=document.id,
                chunk_index=chunk.chunk_index,
                heading_path=chunk.heading_path,
                content=chunk.content,
                content_hash=chunk.content_hash,
            )
        )
    db.commit()
    db.refresh(document)
    return IngestResult(document=document, created=True)


def hash_text(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _split_frontmatter(markdown: str) -> tuple[dict[str, Any], str]:
    if not markdown.startswith("---"):
        return {}, markdown
    lines = markdown.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, markdown
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            raw_frontmatter = "\n".join(lines[1:index])
            body = "\n".join(lines[index + 1 :]).strip()
            loaded = yaml.safe_load(raw_frontmatter) or {}
            if not isinstance(loaded, dict):
                loaded = {}
            return _jsonable(loaded), body
    return {}, markdown


def _extract_title(frontmatter: dict[str, Any], body: str, file_name: str) -> str:
    frontmatter_title = frontmatter.get("title")
    if isinstance(frontmatter_title, str) and frontmatter_title.strip():
        return frontmatter_title.strip()
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip() or Path(file_name).stem
    return Path(file_name).stem


def _chunk_markdown(body: str) -> list[ParsedChunk]:
    sections: list[tuple[str | None, list[str]]] = []
    heading_stack: list[str] = []
    current_heading: str | None = None
    current_lines: list[str] = []

    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            if current_lines:
                sections.append((current_heading, current_lines))
                current_lines = []
            level = len(stripped) - len(stripped.lstrip("#"))
            heading = stripped[level:].strip()
            heading_stack = heading_stack[: max(level - 1, 0)]
            heading_stack.append(heading)
            current_heading = " > ".join(part for part in heading_stack if part)
        current_lines.append(line)

    if current_lines:
        sections.append((current_heading, current_lines))
    if not sections:
        sections.append((None, [body]))

    chunks: list[ParsedChunk] = []
    for index, (heading_path, lines) in enumerate(sections):
        content = "\n".join(lines).strip()
        if not content:
            continue
        chunks.append(
            ParsedChunk(
                chunk_index=len(chunks),
                heading_path=heading_path,
                content=content,
                content_hash=hash_text(content),
            )
        )
    if chunks:
        return chunks
    return [ParsedChunk(chunk_index=0, heading_path=None, content=body, content_hash=hash_text(body))]


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)
