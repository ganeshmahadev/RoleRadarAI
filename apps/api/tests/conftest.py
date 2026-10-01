"""Test configuration.

Tests run against a real PostgreSQL database (`roleradar_test`) so JSONB, enums and
constraints behave as in production. Start it with `docker compose up -d postgres`.
"""

import os
import tempfile
from collections.abc import AsyncIterator
from pathlib import Path

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://roleradar:roleradar@localhost:5433/roleradar_test",
)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["REDIS_URL"] = os.environ.get("TEST_REDIS_URL", "redis://localhost:6379/15")
os.environ["UPLOAD_DIR"] = tempfile.mkdtemp(prefix="roleradar-test-uploads-")

import psycopg  # noqa: E402
import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import make_url, text  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.db.base import Base  # noqa: E402
from app.db.session import get_engine, get_sessionmaker  # noqa: E402
from app.main import create_app  # noqa: E402

API_ROOT = Path(__file__).resolve().parents[1]


def _ensure_database(url: str) -> None:
    parsed = make_url(url)
    admin = parsed.set(drivername="postgresql", database="postgres")
    conninfo = admin.render_as_string(hide_password=False)
    with psycopg.connect(conninfo, autocommit=True) as conn:
        exists = conn.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (parsed.database,)
        ).fetchone()
        if not exists:
            conn.execute(f'CREATE DATABASE "{parsed.database}"')


def _alembic_config() -> Config:
    cfg = Config(str(API_ROOT / "alembic.ini"))
    cfg.attributes["database_url"] = TEST_DATABASE_URL
    cfg.attributes["configure_logger"] = False
    return cfg


@pytest.fixture(scope="session", autouse=True)
def migrated_database() -> None:
    """Rebuild the test schema from migrations (also verifies upgrade/downgrade)."""
    _ensure_database(TEST_DATABASE_URL)
    cfg = _alembic_config()
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")


@pytest.fixture(autouse=True)
async def clean_tables() -> AsyncIterator[None]:
    yield
    tables = [t.name for t in reversed(Base.metadata.sorted_tables)]
    if tables:
        async with get_engine().begin() as conn:
            await conn.execute(text(f"TRUNCATE {', '.join(tables)} RESTART IDENTITY CASCADE"))


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async with get_sessionmaker()() as s:
        yield s


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://test") as c:
        yield c
