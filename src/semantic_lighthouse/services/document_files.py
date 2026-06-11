from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from pathlib import Path

from docx import Document as DocxDocument
from pypdf import PdfReader


class DocumentParseError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedFile:
    markdown: str
    mime_type: str
    parser: str


SUPPORTED_EXTENSIONS = {".md", ".txt", ".pdf", ".docx"}

_READ_CHUNK_SIZE = 65536  # 64 KiB — streaming I/O buffer
_HASH_GUARD_TOLERANCE = 65536  # one extra chunk before declaring mismatch


def hash_bytes(value: bytes) -> str:
    return sha256(value).hexdigest()


def verify_file_hash(path: Path, expected_hash: str, expected_size: int) -> bool:
    """Stream-verify SHA-256 without loading the full file into memory.

    Reads the file in 64 KB chunks so that hash verification does not
    consume memory proportional to file size.  On a 2 GiB ECS this keeps
    concurrent ``complete`` calls from competing for RAM.

    Returns ``False`` early if the file on disk is larger than
    *expected_size* (defense against a client that submitted chunks
    whose total exceeds the declared file size).
    """
    hasher = sha256()
    actual_size = 0
    size_guard = expected_size + _HASH_GUARD_TOLERANCE
    with path.open("rb") as f:
        while chunk := f.read(_READ_CHUNK_SIZE):
            hasher.update(chunk)
            actual_size += len(chunk)
            if actual_size > size_guard:
                return False
    return actual_size == expected_size and hasher.hexdigest() == expected_hash


def supported_document_extension(file_name: str) -> str:
    extension = Path(file_name).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise DocumentParseError("Only MD, TXT, PDF, and DOCX files are supported")
    return extension


def parse_document_bytes(content: bytes, file_name: str) -> ParsedFile:
    extension = supported_document_extension(file_name)
    if extension == ".md":
        return ParsedFile(
            markdown=_decode_utf8(content, "Markdown must be UTF-8 encoded"),
            mime_type="text/markdown",
            parser="markdown",
        )
    if extension == ".txt":
        text = _decode_utf8(content, "Text files must be UTF-8 encoded")
        return ParsedFile(markdown=_plain_text_markdown(text, file_name), mime_type="text/plain", parser="text")
    if extension == ".pdf":
        return ParsedFile(markdown=_pdf_markdown(content, file_name), mime_type="application/pdf", parser="pypdf")
    return ParsedFile(
        markdown=_docx_markdown(content, file_name),
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        parser="python-docx",
    )


def _decode_utf8(content: bytes, error_message: str) -> str:
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise DocumentParseError(error_message) from exc


def _plain_text_markdown(text: str, file_name: str) -> str:
    title = Path(file_name).stem
    return f"# {title}\n\n{text.strip()}"


def _pdf_markdown(content: bytes, file_name: str) -> str:
    try:
        reader = PdfReader(BytesIO(content))
        pages = []
        for index, page in enumerate(reader.pages, start=1):
            text = (page.extract_text() or "").strip()
            if text:
                pages.append(f"## Page {index}\n\n{text}")
    except Exception as exc:
        raise DocumentParseError("PDF text extraction failed") from exc
    if not pages:
        raise DocumentParseError("PDF contains no extractable text")
    return f"# {Path(file_name).stem}\n\n" + "\n\n".join(pages)


def _docx_markdown(content: bytes, file_name: str) -> str:
    try:
        document = DocxDocument(BytesIO(content))
    except Exception as exc:
        raise DocumentParseError("DOCX text extraction failed") from exc
    paragraphs = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]
    if not paragraphs:
        raise DocumentParseError("DOCX contains no extractable text")
    return f"# {Path(file_name).stem}\n\n" + "\n\n".join(paragraphs)
