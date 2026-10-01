import pytest

from app.services.resume_files import DOCX, PDF, TXT
from app.services.resume_parser import (
    DefaultResumeParser,
    ResumeExtractionFailed,
    normalize_text,
    text_hash,
)
from tests.resume_samples import (
    SAMPLE_LINES,
    make_blank_pdf,
    make_docx,
    make_locked_pdf,
    make_pdf,
)

parser = DefaultResumeParser()


def test_pdf_extraction() -> None:
    text = parser.extract(make_pdf(), PDF)
    for line in SAMPLE_LINES:
        assert line in text


def test_multi_page_pdf_keeps_page_order() -> None:
    text = parser.extract(make_pdf(pages=2), PDF)
    assert text.index("(p1)") < text.index("(p2)")


def test_docx_extraction_includes_tables_in_order() -> None:
    data = make_docx(SAMPLE_LINES, table=[["Skill", "Years"], ["Python", "5"]])
    text = parser.extract(data, DOCX)
    assert text.startswith("Alex Example")
    assert "Skill | Years\nPython | 5" in text


def test_txt_extraction_utf8_and_utf16() -> None:
    body = "\n".join(SAMPLE_LINES)
    assert parser.extract(body.encode(), TXT) == normalize_text(body)
    assert parser.extract(body.encode("utf-16"), TXT) == normalize_text(body)


def test_scanned_pdf_without_text_is_rejected() -> None:
    with pytest.raises(ResumeExtractionFailed, match="scanned PDF"):
        parser.extract(make_blank_pdf(), PDF)


def test_password_protected_pdf_is_rejected() -> None:
    with pytest.raises(ResumeExtractionFailed, match="password-protected"):
        parser.extract(make_locked_pdf(), PDF)


def test_damaged_files_are_rejected() -> None:
    with pytest.raises(ResumeExtractionFailed, match="damaged"):
        parser.extract(b"%PDF-1.7 truncated garbage", PDF)
    with pytest.raises(ResumeExtractionFailed, match="damaged"):
        parser.extract(b"PK\x03\x04garbage", DOCX)


def test_normalize_text() -> None:
    raw = "  Ofﬁce   lead\r\n\r\n\r\n\r\nPython\t\tSQL  \x07\n"
    assert normalize_text(raw) == "Office lead\n\nPython SQL"


def test_text_hash_is_stable_sha256() -> None:
    assert text_hash("abc") == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
