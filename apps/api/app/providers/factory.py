from functools import lru_cache

from app.core.config import get_settings
from app.providers.decision import DecisionProvider
from app.providers.openjev import OpenJevProvider


@lru_cache
def get_decision_provider() -> DecisionProvider:
    settings = get_settings()
    return OpenJevProvider(
        settings.openjev_base_url, timeout_seconds=settings.openjev_timeout_seconds
    )
