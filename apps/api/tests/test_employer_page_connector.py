from datetime import UTC, datetime

import httpx
import pytest

from app.connectors.employer_page import EmployerPageConnector
from app.connectors.errors import ExtractionFailed, RobotsDisallowed, UnsupportedSource
from app.connectors.jsonld import find_job_postings
from app.connectors.robots import RobotsPolicy
from app.models import SourceType
from tests.fetch_helpers import by_host, fetcher, fixture, html_response

URL = "https://careers.example.com/jobs/1042"


def connector(routes: dict[str, httpx.Response]) -> EmployerPageConnector:
    f = fetcher(by_host(routes))
    return EmployerPageConnector(f, RobotsPolicy(f))


async def test_imports_jsonld_job_posting() -> None:
    c = connector({"careers.example.com/jobs/1042": html_response(fixture("jsonld_basic.html"))})
    external = await c.fetch_job_by_url(URL)
    assert external.source_type is SourceType.JSONLD
    job = await c.normalize_job(external)

    assert job.title == "Machine Learning Engineer"
    assert job.employer_name == "Example Robotics A/S"
    assert job.location == "Copenhagen, Capital Region, DK"
    assert (job.city, job.country) == ("Copenhagen", "DK")
    assert job.employment_type == "FULL_TIME"
    assert job.workplace_type is None
    assert job.apply_url == "https://careers.example.com/jobs/1042"
    assert job.external_job_id == "REQ-1042"
    assert job.published_at == datetime(2026, 9, 15, tzinfo=UTC)
    assert job.expires_at == datetime(2026, 10, 31, 21, 59, tzinfo=UTC)
    assert job.description.startswith("Example Robotics is hiring a Machine Learning Engineer")
    assert "• Train and evaluate models in PyTorch" in job.description
    assert "<" not in job.description


async def test_imports_jsonld_from_graph_with_escaped_html() -> None:
    c = connector({"careers.example.com/jobs/1042": html_response(fixture("jsonld_graph.html"))})
    job = await c.normalize_job(await c.fetch_job_by_url(URL))
    assert job.title == "Data Scientist & Analyst"
    assert job.employer_name == "Nordic Data ApS"
    assert job.location == "Aarhus, Denmark / Malmö, Sweden"
    assert job.workplace_type == "remote"
    assert job.description.startswith("Join our analytics team")
    assert "• Forecasting" in job.description
    assert job.apply_url == URL  # no url in JSON-LD → the page itself


async def test_incomplete_jsonld_fails_with_manual_paste_hint() -> None:
    c = connector({"careers.example.com/jobs/1042": html_response(fixture("jsonld_broken.html"))})
    with pytest.raises(ExtractionFailed, match="Paste the job description manually"):
        await c.normalize_job(await c.fetch_job_by_url(URL))


def test_find_job_postings_ignores_invalid_json_and_other_types() -> None:
    assert find_job_postings(fixture("jsonld_broken.html"))[0]["title"] == "Stub"
    assert [p["title"] for p in find_job_postings(fixture("jsonld_graph.html"))] == [
        "Data Scientist &amp; Analyst"
    ]
    assert find_job_postings("<html><body>nothing</body></html>") == []


async def test_respects_robots_txt() -> None:
    routes = {
        "careers.example.com/robots.txt": httpx.Response(
            200, text="User-agent: *\nDisallow: /jobs/\n"
        ),
        "careers.example.com/jobs/1042": html_response(fixture("jsonld_basic.html")),
    }
    with pytest.raises(RobotsDisallowed):
        await connector(routes).fetch_job_by_url(URL)


async def test_checks_robots_on_cross_host_redirect() -> None:
    routes = {
        "careers.example.com/jobs/1042": httpx.Response(
            302, headers={"location": "https://ats.example.net/j/1"}
        ),
        "ats.example.net/robots.txt": httpx.Response(200, text="User-agent: *\nDisallow: /\n"),
        "ats.example.net/j/1": html_response(fixture("jsonld_basic.html")),
    }
    with pytest.raises(RobotsDisallowed):
        await connector(routes).fetch_job_by_url(URL)


async def test_rejects_non_html_responses() -> None:
    routes = {
        "careers.example.com/jobs/1042": httpx.Response(
            200, headers={"content-type": "application/pdf"}, content=b"%PDF"
        )
    }
    with pytest.raises(UnsupportedSource, match="application/pdf"):
        await connector(routes).fetch_job_by_url(URL)


async def test_generic_html_fallback() -> None:
    c = connector({"careers.example.com/jobs/1042": html_response(fixture("generic_page.html"))})
    external = await c.fetch_job_by_url(URL)
    assert external.source_type is SourceType.GENERIC_HTML
    job = await c.normalize_job(external)
    assert job.title == "Senior Backend Engineer"  # <h1> preferred over og:title
    assert job.employer_name == "Harbour Logistics"
    assert job.apply_url == URL
    assert job.location is None  # never guessed from free text
    assert job.description.startswith("Senior Backend Engineer\n\nHarbour Logistics is looking")
    assert "• Design and operate Python services on Kubernetes" in job.description
    for noise in ("Careers / Engineering", "Related jobs", "©", "window.tracking"):
        assert noise not in job.description


async def test_generic_fallback_fails_when_no_description() -> None:
    c = connector(
        {"careers.example.com/jobs/1042": html_response(fixture("generic_too_short.html"))}
    )
    with pytest.raises(ExtractionFailed, match="Paste it manually"):
        await c.fetch_job_by_url(URL)
