from enum import StrEnum

from sqlalchemy import Enum


def str_enum(enum: type[StrEnum], name: str) -> Enum:
    """VARCHAR + CHECK constraint (not a native PG enum) storing the enum *values*."""
    return Enum(
        enum,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=32,
        values_callable=lambda members: [m.value for m in members],
        validate_strings=True,
    )
