from collections.abc import Sequence

from app.connectors.base import JobSourceConnector
from app.connectors.errors import UnsupportedSource
from app.connectors.http import validate_url


class ConnectorRegistry:
    """Selects the first connector that handles a URL (PRD §26 priority order)."""

    def __init__(self, connectors: Sequence[JobSourceConnector]) -> None:
        self._connectors = list(connectors)

    def select(self, url: str) -> JobSourceConnector:
        target = validate_url(url)  # SSRF + EURES checks before any connector logic
        for connector in self._connectors:
            if connector.can_handle_url(target.url):
                return connector
        raise UnsupportedSource("No connector can import this URL")
