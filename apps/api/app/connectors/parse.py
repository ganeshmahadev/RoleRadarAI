"""Small parsers shared by connectors. Unknown or malformed values become None (never guessed)."""

from datetime import UTC, date, datetime


def parse_datetime(value: object) -> datetime | None:
    if isinstance(value, (int, float)):  # epoch milliseconds (Lever)
        return datetime.fromtimestamp(value / 1000, tz=UTC)
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        try:
            day = date.fromisoformat(text[:10])
        except ValueError:
            return None
        return datetime(day.year, day.month, day.day, tzinfo=UTC)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def first_str(*values: object) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None
