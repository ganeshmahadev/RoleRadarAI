"""Import every ORM model here so Alembic autogenerate sees it."""

from app.models.company import Company, EuresStatus

__all__ = ["Company", "EuresStatus"]
