import httpx
import pytest

from app.connectors.errors import (
    BlockedUrl,
    EuresNotAllowed,
    FetchFailed,
    InvalidUrl,
    ResponseTooLarge,
    RobotsDisallowed,
)
from app.connectors.http import USER_AGENT, validate_url
from app.connectors.robots import RobotsPolicy
from tests.fetch_helpers import PUBLIC_IP, by_host, fetcher


@pytest.mark.parametrize(
    ("url", "error"),
    [
        ("", InvalidUrl),
        ("not a url", BlockedUrl),
        ("file:///etc/passwd", BlockedUrl),
        ("ftp://example.com/job", BlockedUrl),
        ("javascript:alert(1)", BlockedUrl),
        ("https://user:pw@example.com/job", BlockedUrl),
        ("https://example.com:8443/job", BlockedUrl),
        ("http://localhost/job", BlockedUrl),
        ("http://api.localhost/job", BlockedUrl),
        ("http://127.0.0.1/job", BlockedUrl),
        ("http://10.0.0.5/job", BlockedUrl),
        ("http://192.168.1.10/job", BlockedUrl),
        ("http://172.16.0.1/job", BlockedUrl),
        ("http://169.254.169.254/latest/meta-data", BlockedUrl),
        ("http://100.64.0.1/job", BlockedUrl),
        ("http://[::1]/job", BlockedUrl),
        ("http://[::ffff:127.0.0.1]/job", BlockedUrl),
        ("http://[fd00::1]/job", BlockedUrl),
        ("http://0.0.0.0/job", BlockedUrl),
        ("https://europa.eu/eures/portal/jv-se/jv-details/123", EuresNotAllowed),
        ("https://eures.europa.eu/some/vacancy", EuresNotAllowed),
        ("https://ec.europa.eu/eures/public/job", EuresNotAllowed),
    ],
)
def test_validate_url_rejects(url: str, error: type[Exception]) -> None:
    with pytest.raises(error):
        validate_url(url)


def test_validate_url_accepts_public_https() -> None:
    target = validate_url("  HTTPS://Careers.Example.com/jobs/42?ref=x#apply ")
    assert target.url == "https://careers.example.com/jobs/42?ref=x"
    assert target.host == "careers.example.com"


async def test_connects_to_pinned_ip_with_original_host() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, headers={"content-type": "text/html; charset=utf-8"}, text="ø")

    response = await fetcher(handler).get("https://careers.example.com/jobs/1")
    assert response.text() == "ø"
    assert response.url == "https://careers.example.com/jobs/1"
    request = seen[0]
    assert request.url.host == PUBLIC_IP
    assert request.headers["host"] == "careers.example.com"
    assert request.headers["user-agent"] == USER_AGENT
    assert request.extensions["sni_hostname"] == "careers.example.com"


@pytest.mark.parametrize("addresses", [["10.1.2.3"], [PUBLIC_IP, "127.0.0.1"], ["::1"]])
async def test_blocks_hosts_resolving_to_private_addresses(addresses: list[str]) -> None:
    f = fetcher(lambda r: httpx.Response(200), dns={"evil.example.com": addresses})
    with pytest.raises(BlockedUrl, match="private or reserved"):
        await f.get("https://evil.example.com/job")


async def test_follows_and_revalidates_redirects() -> None:
    routes = {
        "a.example.com/job": httpx.Response(301, headers={"location": "/jobs/2"}),
        "a.example.com/jobs/2": httpx.Response(
            302, headers={"location": "https://b.example.com/x"}
        ),
        "b.example.com/x": httpx.Response(200, text="ok"),
    }
    response = await fetcher(by_host(routes)).get("https://a.example.com/job")
    assert response.url == "https://b.example.com/x"
    assert response.body == b"ok"


@pytest.mark.parametrize(
    ("location", "error"),
    [
        ("http://169.254.169.254/latest/meta-data", BlockedUrl),
        ("http://localhost:8000/admin", BlockedUrl),
        ("file:///etc/passwd", BlockedUrl),
        ("https://europa.eu/eures/portal/jv-se/jv-details/1", EuresNotAllowed),
    ],
)
async def test_rejects_unsafe_redirect_targets(location: str, error: type[Exception]) -> None:
    routes = {"a.example.com/job": httpx.Response(302, headers={"location": location})}
    with pytest.raises(error):
        await fetcher(by_host(routes)).get("https://a.example.com/job")


async def test_redirect_to_host_resolving_privately_is_blocked() -> None:
    routes = {
        "a.example.com/job": httpx.Response(302, headers={"location": "https://inner.example.com/"})
    }
    f = fetcher(by_host(routes), dns={"inner.example.com": ["192.168.0.10"]})
    with pytest.raises(BlockedUrl):
        await f.get("https://a.example.com/job")


async def test_too_many_redirects() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "/again"})

    with pytest.raises(FetchFailed, match="Too many redirects"):
        await fetcher(handler).get("https://a.example.com/job")


@pytest.mark.parametrize(
    ("status", "retryable"), [(404, False), (410, False), (429, True), (503, True)]
)
async def test_http_errors_are_classified(status: int, retryable: bool) -> None:
    with pytest.raises(FetchFailed) as info:
        await fetcher(lambda r: httpx.Response(status)).get("https://a.example.com/job")
    assert info.value.retryable is retryable
    assert info.value.status == status


async def test_timeouts_are_retryable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(FetchFailed) as info:
        await fetcher(handler).get("https://a.example.com/job")
    assert info.value.retryable is True


async def test_response_size_is_bounded() -> None:
    f = fetcher(lambda r: httpx.Response(200, content=b"x" * 2048), max_bytes=1024)
    with pytest.raises(ResponseTooLarge):
        await f.get("https://a.example.com/job")


# --- robots.txt ------------------------------------------------------------------------------

ROBOTS = "User-agent: *\nDisallow: /private\n\nUser-agent: RoleRadarAI\nDisallow: /no-bots\n"


async def test_robots_allows_and_disallows() -> None:
    routes = {"a.example.com/robots.txt": httpx.Response(200, text=ROBOTS)}
    policy = RobotsPolicy(fetcher(by_host(routes)))
    await policy.ensure_allowed("https://a.example.com/jobs/1")
    with pytest.raises(RobotsDisallowed):
        await policy.ensure_allowed("https://a.example.com/no-bots/job")


async def test_robots_disallow_all_for_wildcard_agent() -> None:
    routes = {"a.example.com/robots.txt": httpx.Response(200, text="User-agent: *\nDisallow: /\n")}
    with pytest.raises(RobotsDisallowed, match="Paste the job description manually"):
        await RobotsPolicy(fetcher(by_host(routes))).ensure_allowed("https://a.example.com/jobs/1")


async def test_missing_robots_means_allowed_and_is_cached() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(404)

    policy = RobotsPolicy(fetcher(handler))
    await policy.ensure_allowed("https://a.example.com/jobs/1")
    await policy.ensure_allowed("https://a.example.com/jobs/2")
    assert calls == ["/robots.txt"]


async def test_unreachable_robots_is_treated_as_disallowed() -> None:
    with pytest.raises(RobotsDisallowed, match="Could not read robots.txt"):
        await RobotsPolicy(fetcher(lambda r: httpx.Response(503))).ensure_allowed(
            "https://a.example.com/jobs/1"
        )
