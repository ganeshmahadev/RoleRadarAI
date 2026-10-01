from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Values come from the environment (or a repo-root .env)."""

    model_config = SettingsConfigDict(env_file=("../../.env", ".env"), extra="ignore")

    app_env: str = "development"
    database_url: str
    redis_url: str
    cors_origins: list[str] = ["http://localhost:3000"]

    # OpenJev runs natively on the macOS host (MLX); see docs/ARCHITECTURE.md.
    openjev_base_url: str = "http://localhost:4100"
    openjev_model: str = "openjev/openjev-MLX-4bit"
    # One scoring request asks many questions over a long prompt; allow minutes.
    openjev_timeout_seconds: float = 1800.0
    # "celery" (worker) or "inline" (in the API process; tests and worker-less local runs).
    match_queue: Literal["celery", "inline"] = "celery"
    # Bounded exponential backoff while OpenJev is unavailable during a batch run (P7-004).
    match_retry_delays_seconds: list[float] = [30.0, 60.0, 120.0]
    # Automated discovery (PRD §84, user override for local testing). Off by default.
    discovery_jobspy_enabled: bool = False
    eures_scraper_enabled: bool = False
    discovery_sources: Literal["live", "fake"] = "live"  # "fake" = deterministic E2E data
    discovery_pause_seconds: float = 5.0  # between job-board searches
    eures_crawl_delay_seconds: float = 10.0  # europa.eu robots.txt Crawl-delay
    # How often the SSE progress stream checks the database.
    run_events_poll_seconds: float = 1.0

    upload_dir: str = "./uploads"
    generation_provider: str | None = None
    generation_api_key: SecretStr | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
