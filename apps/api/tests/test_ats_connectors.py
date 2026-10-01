from datetime import UTC, datetime

import httpx
import pytest

from app.connectors.ats import AshbyConnector, GreenhouseConnector, LeverConnector
from app.connectors.errors import FetchFailed
from app.models import SourceType
from tests.fetch_helpers import by_host, fetcher, fixture


def json_response(name: str) -> httpx.Response:
    return httpx.Response(200, headers={"content-type": "application/json"}, text=fixture(name))


GH_URL = "https://job-boards.greenhouse.io/examplefintech/jobs/7001001"
LV_URL = "https://jobs.lever.co/examplecorp/11111111-2222-4333-8444-555555555555"
AB_URL = "https://jobs.ashbyhq.com/exampleco/aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"


@pytest.mark.parametrize(
    ("url", "handled"),
    [
        (GH_URL, True),
        ("https://boards.greenhouse.io/examplefintech/jobs/7001001", True),
        (
            "https://job-boards.eu.greenhouse.io/examplefintech/jobs/7001001",
            False,
        ),  # API unverified
        ("https://stripe.com/jobs/search?gh_jid=8172487", False),  # no board token
        ("https://job-boards.greenhouse.io/examplefintech", False),
    ],
)
def test_greenhouse_url_matching(url: str, handled: bool) -> None:
    assert (
        GreenhouseConnector(fetcher(lambda r: httpx.Response(404))).can_handle_url(url) is handled
    )


async def test_greenhouse_import() -> None:
    routes = {
        "boards-api.greenhouse.io/v1/boards/examplefintech/jobs/7001001": json_response(
            "greenhouse_job.json"
        )
    }
    c = GreenhouseConnector(fetcher(by_host(routes)))
    job = await c.normalize_job(await c.fetch_job_by_url(GH_URL))
    assert job.source_type is SourceType.GREENHOUSE
    assert job.title == "Applied AI Engineer"
    assert job.employer_name == "Example Fintech"
    assert job.location == "Copenhagen, Denmark"
    assert job.external_job_id == "7001001"
    assert job.apply_url == GH_URL
    assert job.published_at == datetime(2026, 9, 3, 17, 30, 34, tzinfo=UTC)
    assert job.description == (
        "About the role\n\nBuild LLM-powered tools for payments risk teams.\n\n"
        "• Python & FastAPI\n• Retrieval-augmented generation"
    )


@pytest.mark.parametrize(
    ("url", "handled"),
    [
        (LV_URL, True),
        (f"{LV_URL}/apply", True),
        ("https://jobs.eu.lever.co/examplecorp/11111111-2222-4333-8444-555555555555", True),
        ("https://jobs.lever.co/examplecorp", False),
    ],
)
def test_lever_url_matching(url: str, handled: bool) -> None:
    assert LeverConnector(fetcher(lambda r: httpx.Response(404))).can_handle_url(url) is handled


async def test_lever_import_uses_regional_api_host() -> None:
    lever_api = "api.eu.lever.co/v0/postings/examplecorp/11111111-2222-4333-8444-555555555555"
    routes = {lever_api: json_response("lever_job.json")}
    c = LeverConnector(fetcher(by_host(routes)))
    url = "https://jobs.eu.lever.co/examplecorp/11111111-2222-4333-8444-555555555555"
    job = await c.normalize_job(await c.fetch_job_by_url(url))
    assert job.title == "Machine Learning Engineer"
    assert job.employer_name is None
    assert job.location == "Aarhus / Copenhagen"
    assert (job.country, job.employment_type, job.workplace_type) == ("DK", "Full-time", "hybrid")
    assert job.apply_url == f"{LV_URL}/apply"
    assert job.published_at == datetime.fromtimestamp(1758000000, tz=UTC)
    assert job.description == (
        "We are building forecasting models for wind farms.\n\n"
        "What you'll do\n• Train time-series models\n• Deploy with MLflow\n\n"
        "Requirements\n• PhD or MSc in ML\n\n"
        "We sponsor work permits where eligible."
    )


async def test_ashby_import_filters_board_by_id() -> None:
    routes = {
        "api.ashbyhq.com/posting-api/job-board/exampleco?includeCompensation=true": json_response(
            "ashby_board.json"
        )
    }
    c = AshbyConnector(fetcher(by_host(routes)))
    assert c.can_handle_url(f"{AB_URL}/application")
    assert not c.can_handle_url("https://jobs.ashbyhq.com/exampleco")
    job = await c.normalize_job(await c.fetch_job_by_url(AB_URL))
    assert job.title == "Senior Data Engineer"
    assert job.location == "Copenhagen / Remote - Denmark"
    assert (job.city, job.country) == ("Copenhagen", "Denmark")
    assert (job.employment_type, job.workplace_type) == ("FullTime", "Hybrid")
    assert job.description == "Own our streaming data platform built on Kafka and dbt."
    assert job.apply_url == f"{AB_URL}/application"


@pytest.mark.parametrize(
    "job_id", ["99999999-8888-4777-8666-555555555555", "00000000-0000-4000-8000-000000000000"]
)
async def test_ashby_unlisted_or_missing_job(job_id: str) -> None:
    routes = {
        "api.ashbyhq.com/posting-api/job-board/exampleco?includeCompensation=true": json_response(
            "ashby_board.json"
        )
    }
    c = AshbyConnector(fetcher(by_host(routes)))
    with pytest.raises(FetchFailed, match="no longer listed") as info:
        await c.fetch_job_by_url(f"https://jobs.ashbyhq.com/exampleco/{job_id}")
    assert info.value.retryable is False


async def test_ats_404_is_not_retryable() -> None:
    c = GreenhouseConnector(fetcher(lambda r: httpx.Response(404)))
    with pytest.raises(FetchFailed) as info:
        await c.fetch_job_by_url(GH_URL)
    assert info.value.retryable is False
