"""Upload validation for resumes (PRD §22, §67): size limit, sniffed file type, safe names.

The client-supplied content type is ignored; the type is decided from the extension and the
file's own bytes, and both must agree.
"""

import io
import re
import unicodedata
import zipfile
from dataclasses import dataclass
from pathlib import PurePosixPath, PureWindowsPath

from app.core.errors import AppError

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_DOCX_UNCOMPRESSED_BYTES = 50 * 1024 * 1024  # zip-bomb guard
MAX_DOCX_ENTRIES = 2000

PDF = "application/pdf"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
TXT = "text/plain"
MIME_BY_EXTENSION = {".pdf": PDF, ".docx": DOCX, ".txt": TXT}

_UNSAFE_CHARS = re.compile(r"[^\w .()\-]+")
_SPACES = re.compile(r"\s+")


class UploadRejected(AppError):
    code = "UPLOAD_REJECTED"


class FileTooLarge(UploadRejected):
    code = "FILE_TOO_LARGE"
    http_status = 413


class EmptyFile(UploadRejected):
    code = "EMPTY_FILE"


class UnsupportedFileType(UploadRejected):
    code = "UNSUPPORTED_FILE_TYPE"


@dataclass(frozen=True)
class ValidatedUpload:
    display_name: str  # sanitized original filename, for display only
    extension: str
    mime_type: str
    data: bytes


def sanitize_filename(raw: str | None) -> str:
    """Display-safe basename: no directories, control characters or odd symbols; ≤ 120 chars."""
    name = PureWindowsPath(PurePosixPath(raw or "").name).name
    name = unicodedata.normalize("NFKC", name)
    name = "".join(ch for ch in name if unicodedata.category(ch)[0] != "C")
    name = _SPACES.sub(" ", _UNSAFE_CHARS.sub("_", name)).strip(" ._")
    if not name:
        return "resume"
    stem, dot, ext = name.rpartition(".")
    if dot and stem and len(ext) <= 10:
        return f"{stem[: 120 - len(ext) - 1]}.{ext}"
    return name[:120]


def _is_docx(data: bytes) -> bool:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_DOCX_ENTRIES:
                return False
            if sum(e.file_size for e in entries) > MAX_DOCX_UNCOMPRESSED_BYTES:
                return False
            names = {e.filename for e in entries}
    except (zipfile.BadZipFile, ValueError):
        return False
    return "[Content_Types].xml" in names and "word/document.xml" in names


def _is_text(data: bytes) -> bool:
    if b"\x00" in data and not data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return False
    for encoding in ("utf-8-sig", "utf-16"):
        try:
            data.decode(encoding)
        except UnicodeDecodeError:
            continue
        if encoding == "utf-16" and not data.startswith((b"\xff\xfe", b"\xfe\xff")):
            continue
        return True
    return False


def validate_upload(filename: str | None, data: bytes) -> ValidatedUpload:
    if len(data) > MAX_UPLOAD_BYTES:
        raise FileTooLarge(f"The file is larger than {MAX_UPLOAD_BYTES // (1024 * 1024)} MB")
    if not data:
        raise EmptyFile("The file is empty")
    display = sanitize_filename(filename)
    extension = PurePosixPath(display.lower()).suffix
    mime = MIME_BY_EXTENSION.get(extension)
    if mime is None:
        raise UnsupportedFileType("Upload a PDF, DOCX or TXT file")
    matches = {
        PDF: lambda: data.startswith(b"%PDF-"),
        DOCX: lambda: _is_docx(data),
        TXT: lambda: _is_text(data),
    }[mime]()
    if not matches:
        raise UnsupportedFileType(f"The file content does not match its {extension} extension")
    return ValidatedUpload(display_name=display, extension=extension, mime_type=mime, data=data)
