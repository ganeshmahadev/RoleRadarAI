import ipaddress
from collections.abc import Callable
from pathlib import Path

import httpx

from app.connectors.http import IpAddress, SafeFetcher

PUBLIC_IP = "93.184.215.14"


def resolver_for(mapping: dict[str, list[str]]) -> Callable[[str], object]:
    async def resolve(host: str) -> list[IpAddress]:
        return [ipaddress.ip_address(a) for a in mapping.get(host, [PUBLIC_IP])]

    return resolve


def fetcher(
    handler: Callable[[httpx.Request], httpx.Response],
    dns: dict[str, list[str]] | None = None,
    max_bytes: int = 5 * 1024 * 1024,
) -> SafeFetcher:
    return SafeFetcher(
        resolver=resolver_for(dns or {}),  # type: ignore[arg-type]
        transport=httpx.MockTransport(handler),
        max_bytes=max_bytes,
    )


def by_host(routes: dict[str, httpx.Response]) -> Callable[[httpx.Request], httpx.Response]:
    """Route mock responses by the original Host header + path (requests go to pinned IPs)."""

    def handler(request: httpx.Request) -> httpx.Response:
        key = f"{request.headers['host']}{request.url.raw_path.decode()}"
        return routes.get(key, httpx.Response(404))

    return handler


FIXTURES = Path(__file__).parent / "fixtures" / "jobs"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def html_response(body: str) -> httpx.Response:
    return httpx.Response(200, headers={"content-type": "text/html; charset=utf-8"}, text=body)
