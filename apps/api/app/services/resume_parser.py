"""ResumeParser boundary (PRD §73): file bytes → normalized plain text.

Deterministic extraction only (PyMuPDF for PDF, python-docx for DOCX). No AI involved.
"""

import hashlib
import io
import re
import unicodedata
from typing import Protocol

import pymupdf
from docx import Document
from docx.table import Table

from app.core.errors import AppError
from app.services.resume_files import DOCX, PDF, TXT

MAX_PDF_PAGES = 50
MIN_TEXT_CHARS = 50
MAX_TEXT_CHARS = 200_000

_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")
_TRAILING = re.compile(r"[ \t]+\n")
_INLINE_SPACE = re.compile(r"[ \t ]+")
_BLANK_LINES = re.compile(r"\n{3,}")


class ResumeExtractionFailed(AppError):
    code = "RESUME_EXTRACTION_FAILED"


class ResumeParser(Protocol):
    def extract(self, data: bytes, mime_type: str) -> str: ...


def normalize_text(raw: str) -> str:
    """NFKC (expands PDF ligatures), unified newlines, no control chars, tidy whitespace."""
    text = unicodedata.normalize("NFKC", raw).replace("\r\n", "\n").replace("\r", "\n")
    text = _CONTROL.sub("", text)
    text = _INLINE_SPACE.sub(" ", text)
    text = _TRAILING.sub("\n", text + "\n")
    lines = [line.strip() for line in text.split("\n")]
    return _BLANK_LINES.sub("\n\n", "\n".join(lines)).strip()


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _pdf_text(data: bytes) -> str:
    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
    except Exception as exc:  # PyMuPDF raises various types for corrupt files
        raise ResumeExtractionFailed("The PDF could not be opened; it may be damaged") from exc
    with doc:
        if doc.needs_pass:
            raise ResumeExtractionFailed("The PDF is password-protected; upload an unlocked copy")
        if doc.page_count > MAX_PDF_PAGES:
            raise ResumeExtractionFailed(f"The PDF has more than {MAX_PDF_PAGES} pages")
        pages = (doc.load_page(i).get_text("text", sort=True) for i in range(doc.page_count))
        return "\n\n".join(pages)


def _docx_text(data: bytes) -> str:
    try:
        document = Document(io.BytesIO(data))
    except Exception as exc:
        raise ResumeExtractionFailed("The DOCX file could not be read; it may be damaged") from exc
    blocks: list[str] = []
    for block in document.iter_inner_content():
        if isinstance(block, Table):
            for row in block.rows:
                cells: list[str] = []
                for cell in row.cells:  # merged cells repeat; keep each value once
                    value = cell.text.strip()
                    if value and value not in cells:
                        cells.append(value)
                if cells:
                    blocks.append(" | ".join(cells))
        else:
            blocks.append(block.text)
    return "\n".join(blocks)


def _txt_text(data: bytes) -> str:
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16")
    return data.decode("utf-8-sig")


class DefaultResumeParser:
    def extract(self, data: bytes, mime_type: str) -> str:
        readers = {PDF: _pdf_text, DOCX: _docx_text, TXT: _txt_text}
        reader = readers.get(mime_type)
        if reader is None:
            raise ResumeExtractionFailed(f"Unsupported resume type {mime_type}")
        text = normalize_text(reader(data))
        if len(text) < MIN_TEXT_CHARS:
            raise ResumeExtractionFailed(
                "No readable text was found. If this is a scanned PDF, upload a text-based "
                "PDF, DOCX or TXT version instead."
            )
        if len(text) > MAX_TEXT_CHARS:
            raise ResumeExtractionFailed("The resume text is too long to process")
        return text
