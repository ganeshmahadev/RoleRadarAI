import io
import os
import stat
import zipfile
from pathlib import Path

import pytest

from app.providers.storage import LocalStorageProvider, StorageError
from app.services.resume_files import (
    DOCX,
    MAX_UPLOAD_BYTES,
    PDF,
    TXT,
    EmptyFile,
    FileTooLarge,
    UnsupportedFileType,
    sanitize_filename,
    validate_upload,
)
from tests.resume_samples import make_docx, make_pdf


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Alex CV.pdf", "Alex CV.pdf"),
        ("../../etc/passwd", "passwd"),
        ("C:\\Users\\alex\\resume final.docx", "resume final.docx"),
        ("résumé<script>.pdf", "résumé_script_.pdf"),
        ("bad\x00name\n.txt", "badname.txt"),
        ("...hidden.pdf", "hidden.pdf"),
        ("", "resume"),
        (None, "resume"),
        ("a" * 300 + ".pdf", "a" * 116 + ".pdf"),
    ],
)
def test_sanitize_filename(raw: str | None, expected: str) -> None:
    assert sanitize_filename(raw) == expected


@pytest.mark.parametrize(
    ("name", "data", "mime"),
    [
        ("cv.pdf", make_pdf(), PDF),
        ("CV.PDF", make_pdf(), PDF),
        ("cv.docx", make_docx(), DOCX),
        ("cv.txt", "Alex Example — Python".encode(), TXT),
        ("cv.txt", "\ufeffAlex".encode(), TXT),
        ("cv.txt", "Alex Ø".encode("utf-16"), TXT),
    ],
)
def test_accepts_matching_types(name: str, data: bytes, mime: str) -> None:
    assert validate_upload(name, data).mime_type == mime


@pytest.mark.parametrize(
    ("name", "data"),
    [
        ("cv.exe", b"MZ\x90\x00"),
        ("cv.pdf", make_docx()),  # extension and content disagree
        ("cv.docx", make_pdf()),
        ("cv.docx", b"PK\x03\x04 not really a zip"),
        ("cv.txt", b"\x00\x01binary"),
        ("cv.txt", b"\xc3\x28 invalid utf8 \xa0\xa1"),
        ("cv.html", b"<html></html>"),
        ("cv", b"%PDF-1.7"),
    ],
)
def test_rejects_unsupported_or_mismatched(name: str, data: bytes) -> None:
    with pytest.raises(UnsupportedFileType):
        validate_upload(name, data)


def test_rejects_zip_that_is_not_a_word_document() -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("readme.txt", "hello")
    with pytest.raises(UnsupportedFileType):
        validate_upload("cv.docx", buffer.getvalue())


def test_rejects_docx_zip_bomb() -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", "<w/>")
        archive.writestr("word/huge.bin", b"\x00" * (60 * 1024 * 1024))
    assert len(buffer.getvalue()) < MAX_UPLOAD_BYTES
    with pytest.raises(UnsupportedFileType):
        validate_upload("cv.docx", buffer.getvalue())


def test_size_and_empty_limits() -> None:
    with pytest.raises(FileTooLarge) as info:
        validate_upload("cv.txt", b"a" * (MAX_UPLOAD_BYTES + 1))
    assert info.value.http_status == 413
    with pytest.raises(EmptyFile):
        validate_upload("cv.txt", b"")


# --- storage ---------------------------------------------------------------------------------


def test_local_storage_round_trip_with_private_permissions(tmp_path: Path) -> None:
    storage = LocalStorageProvider(tmp_path / "uploads")
    key = storage.save(b"%PDF-data", folder="resumes", suffix=".pdf")
    assert key.startswith("resumes/") and key.endswith(".pdf")
    path = tmp_path / "uploads" / key
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600
    assert stat.S_IMODE(os.stat(path.parent).st_mode) == 0o700
    assert storage.read(key) == b"%PDF-data"
    storage.delete(key)
    assert not path.exists()
    storage.delete(key)  # idempotent


def test_storage_keys_are_unique(tmp_path: Path) -> None:
    storage = LocalStorageProvider(tmp_path)
    keys = {storage.save(b"x", folder="resumes", suffix=".txt") for _ in range(20)}
    assert len(keys) == 20


@pytest.mark.parametrize("key", ["../outside.pdf", "/etc/passwd", "resumes/../../x", ""])
def test_storage_rejects_keys_outside_root(tmp_path: Path, key: str) -> None:
    storage = LocalStorageProvider(tmp_path / "uploads")
    with pytest.raises(StorageError):
        storage.read(key)


@pytest.mark.parametrize(
    ("folder", "suffix"), [("../x", ".pdf"), ("resumes", "/../x"), ("a/b", "")]
)
def test_storage_rejects_unsafe_folder_or_suffix(tmp_path: Path, folder: str, suffix: str) -> None:
    with pytest.raises(StorageError):
        LocalStorageProvider(tmp_path).save(b"x", folder=folder, suffix=suffix)
