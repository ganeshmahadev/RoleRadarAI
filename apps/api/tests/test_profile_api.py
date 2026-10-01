import pytest
from httpx import AsyncClient

from tests.resume_samples import make_pdf


@pytest.fixture
async def resume_id(client: AsyncClient) -> str:
    response = await client.post(
        "/api/v1/resumes", files={"file": ("cv.pdf", make_pdf(), "application/pdf")}
    )
    assert response.status_code == 201
    value: str = response.json()["id"]
    return value


async def test_new_profile_is_empty(client: AsyncClient, resume_id: str) -> None:
    body = (await client.get(f"/api/v1/resumes/{resume_id}/profile")).json()
    assert body["resume_id"] == resume_id
    assert body["skills"] == [] and body["languages"] == []
    assert body["years_experience"] is None and body["remote_preference"] is None


async def test_full_update_and_cleanup(client: AsyncClient, resume_id: str) -> None:
    payload = {
        "target_roles": ["  ML Engineer ", "Applied AI Engineer", "ml engineer", ""],
        "skills": ["Python", "PyTorch"],
        "years_experience": 5.5,
        "industries": ["Fintech"],
        "education": ["MSc Computer Science, Aarhus University"],
        "certifications": ["AWS SAA"],
        "languages": [
            {"language": "English", "level": "C2"},
            {"language": "Danish", "level": "A2"},
            {"language": "english", "level": "B2"},
        ],
        "preferred_locations": ["Copenhagen", "Aarhus"],
        "remote_preference": "hybrid",
        "work_authorization": ["Fast-track work permit (sponsorship required)"],
    }
    response = await client.patch(f"/api/v1/resumes/{resume_id}/profile", json=payload)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["target_roles"] == ["ML Engineer", "Applied AI Engineer"]
    assert body["languages"] == [
        {"language": "English", "level": "C2"},
        {"language": "Danish", "level": "A2"},
    ]
    assert body["years_experience"] == "5.5"
    assert body["remote_preference"] == "hybrid"

    persisted = (await client.get(f"/api/v1/resumes/{resume_id}/profile")).json()
    assert persisted["skills"] == ["Python", "PyTorch"]


async def test_partial_update_and_clearing(client: AsyncClient, resume_id: str) -> None:
    url = f"/api/v1/resumes/{resume_id}/profile"
    await client.patch(
        url, json={"skills": ["Python"], "years_experience": 3, "remote_preference": "remote"}
    )
    body = (await client.patch(url, json={"industries": ["Energy"]})).json()
    assert body["skills"] == ["Python"]  # untouched
    cleared = (
        await client.patch(
            url, json={"skills": None, "years_experience": None, "remote_preference": None}
        )
    ).json()
    assert cleared["skills"] == []
    assert cleared["years_experience"] is None
    assert cleared["remote_preference"] is None
    assert cleared["industries"] == ["Energy"]


@pytest.mark.parametrize(
    "payload",
    [
        {"years_experience": -1},
        {"years_experience": 61},
        {"years_experience": 2.25},
        {"remote_preference": "moon"},
        {"languages": [{"language": "Danish", "level": "fluent"}]},
        {"languages": [{"language": " ", "level": "B2"}]},
        {"skills": ["x" * 101]},
        {"skills": [f"s{i}" for i in range(51)]},
        {"hobbies": ["chess"]},
    ],
)
async def test_invalid_updates_are_rejected(
    client: AsyncClient, resume_id: str, payload: dict[str, object]
) -> None:
    response = await client.patch(f"/api/v1/resumes/{resume_id}/profile", json=payload)
    assert response.status_code == 422


async def test_profile_of_unknown_resume_is_404(client: AsyncClient) -> None:
    missing = "00000000-0000-4000-8000-000000000000"
    assert (await client.get(f"/api/v1/resumes/{missing}/profile")).status_code == 404
    assert (await client.patch(f"/api/v1/resumes/{missing}/profile", json={})).status_code == 404
