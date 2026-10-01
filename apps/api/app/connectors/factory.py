from functools import lru_cache

from app.connectors.ats import AshbyConnector, GreenhouseConnector, LeverConnector
from app.connectors.employer_page import EmployerPageConnector
from app.connectors.http import SafeFetcher
from app.connectors.registry import ConnectorRegistry
from app.connectors.robots import RobotsPolicy


def build_registry(fetcher: SafeFetcher) -> ConnectorRegistry:
    """PRD §26 order: structured ATS APIs first, then the employer page (JSON-LD → generic)."""
    return ConnectorRegistry(
        [
            GreenhouseConnector(fetcher),
            LeverConnector(fetcher),
            AshbyConnector(fetcher),
            EmployerPageConnector(fetcher, RobotsPolicy(fetcher)),
        ]
    )


@lru_cache
def get_registry() -> ConnectorRegistry:
    return build_registry(SafeFetcher())
