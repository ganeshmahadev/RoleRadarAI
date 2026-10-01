from functools import lru_cache

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

    upload_dir: str = "./uploads"
    generation_provider: str | None = None
    generation_api_key: SecretStr | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
