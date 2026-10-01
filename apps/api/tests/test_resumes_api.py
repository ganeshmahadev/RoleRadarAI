import logging
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import CandidateProfile, RemotePreference, Resume
from tests.resume_samples import make_blank_pdf, make_docx, make_pdf

PDF_MIME = "application/pdf"


async def upload(
    client: AsyncClient, data: bytes, filename: str = "Alex CV.pdf", **form: str
) -> dict[str, object]:
    response = await client.post(
        "/api/v1/resumes", files={"file": (filename, data, PDF_MIME)}, data=form
    )
    assert response.status_code == 201, response.text
    body: dict[str, object] = response.json()
    return body


def stored_file(resume: Resume) -> Path:
    return Path(get_settings().upload_dir) / resume.file_path


def uploaded_files() -> set[Path]:
    return set(Path(get_settings().upload_dir).rglob("*"))


async def test_upload_extracts_and_stores(client: AsyncClient, session: AsyncSession) -> None:
    body = await upload(client, make_pdf())
    assert body["name"] == "Alex CV"
    assert body["original_filename"] == "Alex CV.pdf"
    assert body["mime_type"] == PDF_MIME
    assert body["is_primary"] is True  # first resume becomes primary
    assert "Alex Example" in str(body["raw_text"])
    assert body["text_chars"] == len(str(body["raw_text"]))

    resume = await session.get_one(Resume, body["id"])
    assert stored_file(resume).read_bytes()[:5] == b"%PDF-"
    assert "/" not in resume.file_path.removeprefix("resumes/")
    assert resume.profile is not None


async def test_upload_uses_given_name_and_ignores_client_content_type(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/resumes",
        files={"file": ("cv.docx", make_docx(), "application/x-anything")},
        data={"name": "Backend focus"},
    )
    assert response.status_code == 201
    assert response.json()["name"] == "Backend focus"
    assert response.json()["mime_type"].endswith("wordprocessingml.document")


@pytest.mark.parametrize(
    ("filename", "data", "status", "code"),
    [
        ("cv.exe", b"MZ\x90", 422, "UNSUPPORTED_FILE_TYPE"),
        ("cv.pdf", make_docx(), 422, "UNSUPPORTED_FILE_TYPE"),
        ("cv.pdf", b"", 422, "EMPTY_FILE"),
        ("cv.pdf", make_blank_pdf(), 422, "RESUME_EXTRACTION_FAILED"),
        ("cv.txt", b"x" * (10 * 1024 * 1024 + 1), 413, "FILE_TOO_LARGE"),
    ],
)
async def test_rejected_uploads_store_nothing(
    client: AsyncClient, session: AsyncSession, filename: str, data: bytes, status: int, code: str
) -> None:
    files_before = uploaded_files()
    response = await client.post("/api/v1/resumes", files={"file": (filename, data, PDF_MIME)})
    assert response.status_code == status
    assert response.json()["detail"]["code"] == code
    assert await session.scalar(select(func.count()).select_from(Resume)) == 0
    assert uploaded_files() == files_before


async def test_upload_requires_a_file(client: AsyncClient) -> None:
    assert (await client.post("/api/v1/resumes")).status_code == 422


async def test_list_detail_and_primary_switch(client: AsyncClient) -> None:
    first = await upload(client, make_pdf(), "first.pdf")
    second = await upload(client, make_docx(), "second.docx")
    assert second["is_primary"] is False

    listing = (await client.get("/api/v1/resumes")).json()
    assert [r["name"] for r in listing] == ["second", "first"]  # newest first
    assert "raw_text" not in listing[0]

    switched = (await client.post(f"/api/v1/resumes/{second['id']}/set-primary")).json()
    assert switched["is_primary"] is True
    flags = {r["name"]: r["is_primary"] for r in (await client.get("/api/v1/resumes")).json()}
    assert flags == {"first": False, "second": True}

    detail = (await client.get(f"/api/v1/resumes/{first['id']}")).json()
    assert "Alex Example" in detail["raw_text"]


async def test_new_resume_profile_starts_from_primary_profile(
    client: AsyncClient, session: AsyncSession
) -> None:
    first = await upload(client, make_pdf())
    profile = await session.scalar(
        select(CandidateProfile).where(CandidateProfile.resume_id == first["id"])
    )
    assert profile is not None
    profile.skills = ["Python"]
    profile.remote_preference = RemotePreference.HYBRID
    await session.commit()

    second = await upload(client, make_docx(), "second.docx")
    copied = await session.scalar(
        select(CandidateProfile).where(CandidateProfile.resume_id == second["id"])
    )
    assert copied is not None
    assert copied.skills == ["Python"]
    assert copied.remote_preference is RemotePreference.HYBRID
    assert copied.id != profile.id


async def test_delete_removes_file_and_promotes_newest(
    client: AsyncClient, session: AsyncSession
) -> None:
    first = await upload(client, make_pdf(), "first.pdf")
    await upload(client, make_docx(), "second.docx")
    third = await upload(client, make_pdf(), "third.pdf")
    resume = await session.get_one(Resume, first["id"])
    path = stored_file(resume)
    assert path.exists()

    assert (await client.delete(f"/api/v1/resumes/{first['id']}")).status_code == 204
    assert not path.exists()
    assert (await client.get(f"/api/v1/resumes/{first['id']}")).status_code == 404
    remaining = {r["name"]: r["is_primary"] for r in (await client.get("/api/v1/resumes")).json()}
    assert remaining == {"third": True, "second": False}
    assert third["is_primary"] is False  # it was not primary when uploaded


async def test_resume_text_is_never_logged(
    client: AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.DEBUG):
        await upload(client, make_pdf())
    logged = " ".join(f"{record.getMessage()} {record.__dict__}" for record in caplog.records)
    assert "resume_uploaded" in logged
    assert "Alex Example" not in logged


async def test_unknown_resume_is_404(client: AsyncClient) -> None:
    missing = "00000000-0000-4000-8000-000000000000"
    assert (await client.get(f"/api/v1/resumes/{missing}")).status_code == 404
    assert (await client.post(f"/api/v1/resumes/{missing}/set-primary")).status_code == 404
    assert (await client.delete(f"/api/v1/resumes/{missing}")).status_code == 404
