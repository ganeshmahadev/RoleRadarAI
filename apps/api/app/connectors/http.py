"""SSRF-safe HTTP retrieval for user-submitted job URLs (PRD §67, ARCHITECTURE §6).

- http/https only, default ports only, no credentials in URLs
- every resolved address must be public (blocks loopback, RFC1918, link-local,
  CGNAT, multicast, reserved and cloud metadata addresses)
- connects to the validated IP (Host header + TLS SNI keep the original name),
  so DNS rebinding cannot swap in a private address after validation
- redirects are followed manually and every hop is re-validated
- bounded timeouts and response size
- EURES hosts are rejected outright (PRD §8)
"""

import asyncio
import ipaddress
import socket
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx

from app.connectors.errors import (
    BlockedUrl,
    EuresNotAllowed,
    FetchFailed,
    InvalidUrl,
    ResponseTooLarge,
)

USER_AGENT = "RoleRadarAI/0.1 (personal job-search tool; single user-initiated fetch)"
ALLOWED_PORTS = {"http": 80, "https": 443}
MAX_REDIRECTS = 5
MAX_BYTES = 5 * 1024 * 1024
TIMEOUT = httpx.Timeout(10.0, connect=5.0)

IpAddress = ipaddress.IPv4Address | ipaddress.IPv6Address
Resolver = Callable[[str], Awaitable[list[IpAddress]]]


async def system_resolver(host: str) -> list[IpAddress]:
    loop = asyncio.get_running_loop()
    try:
        infos = await loop.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise FetchFailed(f"Could not resolve {host}", retryable=False) from exc
    return [ipaddress.ip_address(info[4][0]) for info in infos]


def is_public_address(address: IpAddress) -> bool:
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
        return is_public_address(address.ipv4_mapped)
    return address.is_global and not address.is_multicast


def is_eures_url(host: str, path: str) -> bool:
    host = host.lower().rstrip(".")
    if "eures" in host:
        return True
    return (host == "europa.eu" or host.endswith(".europa.eu")) and "/eures" in path.lower()


@dataclass(frozen=True)
class ValidatedUrl:
    url: str
    scheme: str
    host: str
    path: str


def validate_url(raw: str) -> ValidatedUrl:
    url = raw.strip()
    if not url or len(url) > 2048:
        raise InvalidUrl("Enter a valid http(s) URL")
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError as exc:
        raise InvalidUrl("Enter a valid http(s) URL") from exc
    scheme = parts.scheme.lower()
    if scheme not in ALLOWED_PORTS:
        raise BlockedUrl(f"Only http and https URLs are allowed (got {scheme or 'none'}://)")
    if not parts.hostname:
        raise InvalidUrl("URL has no host")
    if parts.username or parts.password:
        raise BlockedUrl("URLs with credentials are not allowed")
    if port is not None and port != ALLOWED_PORTS[scheme]:
        raise BlockedUrl("Only default ports (80/443) are allowed")
    host = parts.hostname.lower()
    if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
        raise BlockedUrl("Local hostnames are not allowed")
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None and not is_public_address(literal):
        raise BlockedUrl("Private, loopback and link-local addresses are not allowed")
    if is_eures_url(host, parts.path):
        raise EuresNotAllowed(
            "EURES vacancy pages cannot be imported. Open the original employer or ATS "
            "posting and import that URL instead."
        )
    path = parts.path or "/"
    normalized = urlunsplit((scheme, parts.netloc.lower(), path, parts.query, ""))
    return ValidatedUrl(url=normalized, scheme=scheme, host=host, path=path)


@dataclass(frozen=True)
class FetchResponse:
    url: str  # final URL after redirects
    status: int
    content_type: str
    body: bytes

    def text(self) -> str:
        charset = "utf-8"
        for part in self.content_type.split(";")[1:]:
            key, _, value = part.strip().partition("=")
            if key.lower() == "charset" and value:
                charset = value.strip('"')
        return self.body.decode(charset, errors="replace")


@dataclass(frozen=True)
class _Redirect:
    location: str


class SafeFetcher:
    def __init__(
        self,
        resolver: Resolver = system_resolver,
        transport: httpx.AsyncBaseTransport | None = None,
        max_bytes: int = MAX_BYTES,
    ) -> None:
        self._resolver = resolver
        self._transport = transport
        self._max_bytes = max_bytes

    async def _pinned_ip(self, target: ValidatedUrl) -> IpAddress:
        try:
            return ipaddress.ip_address(target.host)
        except ValueError:
            pass
        addresses = await self._resolver(target.host)
        if not addresses:
            raise FetchFailed(f"Could not resolve {target.host}", retryable=False)
        if not all(is_public_address(a) for a in addresses):
            raise BlockedUrl(f"{target.host} resolves to a private or reserved address")
        return addresses[0]

    async def get(
        self, url: str, *, accept: str = "text/html,application/json;q=0.9,*/*;q=0.5"
    ) -> FetchResponse:
        current = validate_url(url)
        async with httpx.AsyncClient(
            transport=self._transport, timeout=TIMEOUT, follow_redirects=False
        ) as client:
            for _ in range(MAX_REDIRECTS + 1):
                result = await self._request(client, current, accept)
                if isinstance(result, _Redirect):
                    current = validate_url(urljoin(current.url, result.location))
                    continue
                return result
        raise FetchFailed("Too many redirects", retryable=False)

    async def _request(
        self, client: httpx.AsyncClient, target: ValidatedUrl, accept: str
    ) -> FetchResponse | _Redirect:
        ip = await self._pinned_ip(target)
        ip_host = f"[{ip}]" if ip.version == 6 else str(ip)
        parts = urlsplit(target.url)
        pinned_url = urlunsplit((parts.scheme, ip_host, parts.path, parts.query, ""))
        headers = {"Host": parts.netloc, "User-Agent": USER_AGENT, "Accept": accept}
        extensions = {"sni_hostname": target.host} if target.scheme == "https" else {}
        try:
            async with client.stream(
                "GET", pinned_url, headers=headers, extensions=extensions
            ) as response:
                if response.is_redirect:
                    location = response.headers.get("location")
                    if not location:
                        raise FetchFailed("Redirect without a Location header", retryable=False)
                    return _Redirect(location)
                if response.status_code >= 400:
                    raise FetchFailed(
                        f"{target.host} returned HTTP {response.status_code}",
                        retryable=response.status_code >= 500 or response.status_code == 429,
                        status=response.status_code,
                    )
                declared = response.headers.get("content-length")
                if declared and declared.isdigit() and int(declared) > self._max_bytes:
                    raise ResponseTooLarge("The page is too large to import")
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > self._max_bytes:
                        raise ResponseTooLarge("The page is too large to import")
                return FetchResponse(
                    url=target.url,
                    status=response.status_code,
                    content_type=response.headers.get("content-type", ""),
                    body=bytes(body),
                )
        except httpx.TimeoutException as exc:
            raise FetchFailed(f"Timed out fetching {target.host}", retryable=True) from exc
        except httpx.TransportError as exc:
            raise FetchFailed(f"Could not connect to {target.host}", retryable=True) from exc
