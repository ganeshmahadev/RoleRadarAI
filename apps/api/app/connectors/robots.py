"""robots.txt policy for generic employer pages (PRD §26 "permitted" source).

Follows RFC 9309 semantics: 4xx → allowed; 5xx/unreachable → disallowed.
Documented public ATS APIs (Greenhouse, Lever, Ashby) are not subject to this check.
"""

import time
from urllib.parse import urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

from app.connectors.errors import FetchFailed, RobotsDisallowed, SourceError
from app.connectors.http import USER_AGENT, SafeFetcher

ROBOTS_AGENT = "RoleRadarAI"
CACHE_SECONDS = 3600


class RobotsPolicy:
    def __init__(self, fetcher: SafeFetcher) -> None:
        self._fetcher = fetcher
        self._cache: dict[str, tuple[float, RobotFileParser | None]] = {}

    async def ensure_allowed(self, url: str) -> None:
        parts = urlsplit(url)
        origin = urlunsplit((parts.scheme, parts.netloc, "", "", ""))
        parser = await self._parser(origin)
        if parser is None:
            return
        if not (parser.can_fetch(ROBOTS_AGENT, url) and parser.can_fetch(USER_AGENT, url)):
            raise RobotsDisallowed(
                f"{parts.hostname} does not allow automated retrieval of this page "
                "(robots.txt). Paste the job description manually instead."
            )

    async def _parser(self, origin: str) -> RobotFileParser | None:
        cached = self._cache.get(origin)
        if cached and time.monotonic() - cached[0] < CACHE_SECONDS:
            return cached[1]
        parser: RobotFileParser | None
        try:
            response = await self._fetcher.get(f"{origin}/robots.txt", accept="text/plain")
        except FetchFailed as exc:
            if exc.status is not None and 400 <= exc.status < 500:
                parser = None  # no robots.txt: everything allowed
            else:
                raise RobotsDisallowed(
                    "Could not read robots.txt for this site, so it is treated as disallowed. "
                    "Paste the job description manually instead."
                ) from exc
        except SourceError:
            raise
        else:
            parser = RobotFileParser()
            parser.parse(response.text().splitlines())
        self._cache[origin] = (time.monotonic(), parser)
        return parser
