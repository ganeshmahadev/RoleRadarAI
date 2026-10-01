import pytest

from app.connectors.base import ExternalJob, JobSourceConnector, NormalizedJob, UrlImportConnector
from app.connectors.errors import (
    BlockedUrl,
    EuresNotAllowed,
    UnsupportedOperation,
    UnsupportedSource,
)
from app.connectors.eures import EuresDiscoveryConnector
from app.connectors.registry import ConnectorRegistry
from app.connectors.text import clean_text, html_to_text
from app.models import Company, SourceType


class FakeConnector(UrlImportConnector):
    def __init__(self, name: str, host: str) -> None:
        self.name = name
        self.host = host

    def can_handle_url(self, url: str) -> bool:
        return self.host in url

    async def fetch_job_by_url(self, url: str) -> ExternalJob:
        return ExternalJob(SourceType.MANUAL, url, url, None, {})

    async def normalize_job(self, external_job: ExternalJob) -> NormalizedJob:
        return NormalizedJob(
            SourceType.MANUAL, external_job.source_url, external_job.final_url, "t", "d"
        )


def test_registry_selects_first_matching_connector() -> None:
    a, b = FakeConnector("a", "ats.example"), FakeConnector("b", "example")
    registry = ConnectorRegistry([a, b])
    assert registry.select("https://ats.example.com/job/1") is a
    assert registry.select("https://www.example.org/job/1") is b
    with pytest.raises(UnsupportedSource):
        ConnectorRegistry([a]).select("https://other.org/job")


def test_registry_validates_url_before_selecting() -> None:
    registry = ConnectorRegistry([FakeConnector("any", "")])
    with pytest.raises(BlockedUrl):
        registry.select("http://127.0.0.1/job")
    with pytest.raises(EuresNotAllowed):
        registry.select("https://europa.eu/eures/portal/jv-se/jv-details/1")


async def test_url_connectors_do_not_support_company_search() -> None:
    connector = FakeConnector("fake", "x")
    assert isinstance(connector, JobSourceConnector)
    with pytest.raises(UnsupportedOperation):
        await connector.search_company(Company())
    with pytest.raises(UnsupportedOperation):
        await connector.fetch_job("123")


async def test_eures_connector_only_builds_urls() -> None:
    connector = EuresDiscoveryConnector()
    assert isinstance(connector, JobSourceConnector)
    company = Company(company_name="3Shape A/S")
    assert connector.search_url(company).endswith(
        "keywordsEverywhere=3Shape+A%2FS&publicationPeriod=LAST_MONTH&previousPageType=findJob&lang=en"
    )
    assert connector.can_handle_url("https://europa.eu/eures/portal/jv-se/jv-details/1") is False
    for call in (
        connector.search_company(company),
        connector.fetch_job("1"),
        connector.fetch_job_by_url("https://europa.eu/eures/x"),
    ):
        with pytest.raises(UnsupportedOperation, match="not retrieved"):
            await call


def test_html_to_text() -> None:
    markup = """
      <div><h2>About&nbsp;us</h2><p>We build <b>models</b>.</p>
      <script>alert(1)</script><style>p{}</style>
      <ul><li>Python</li><li>PyTorch</li></ul><p>Apply&amp;join</p></div>
    """
    assert (
        html_to_text(markup) == "About us\n\nWe build models.\n\n• Python\n• PyTorch\n\nApply&join"
    )


def test_html_to_text_unescapes_escaped_html() -> None:
    assert html_to_text(
        "&lt;p&gt;Hello&lt;/p&gt;&lt;p&gt;World&lt;/p&gt;", unescape_first=True
    ) == ("Hello\n\nWorld")


def test_clean_text() -> None:
    assert clean_text("  Copenhagen &amp; Aarhus\t ") == "Copenhagen & Aarhus"
    assert clean_text("   ") is None
    assert clean_text(42) is None


def test_normalized_snapshot_is_json_ready() -> None:
    from datetime import UTC, datetime

    job = NormalizedJob(
        SourceType.LEVER, "u", "f", "Title", "Desc", published_at=datetime(2026, 1, 2, tzinfo=UTC)
    )
    snap = job.snapshot()
    assert snap["source_type"] == "lever"
    assert snap["published_at"] == "2026-01-02T00:00:00+00:00"
