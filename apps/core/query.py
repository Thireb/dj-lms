"""Safe values from the query string (audit M3).

PostgreSQL rejects NUL bytes, int() accepts digits like "²", and a huge
number overflows a bigint. All of these gave a 500 before.
"""

from __future__ import annotations

MAX_ID_DIGITS = 18  # fits a PostgreSQL bigint
MAX_SEARCH_LENGTH = 100


def id_param(value: str | None) -> int | None:
    """A positive whole number in plain ASCII digits, or None."""
    value = (value or "").strip()
    if 0 < len(value) <= MAX_ID_DIGITS and value.isascii() and value.isdigit():
        return int(value)
    return None


def search_param(value: str | None) -> str:
    """Search text without NUL bytes, trimmed and capped in length."""
    return (value or "").replace("\x00", "").strip()[:MAX_SEARCH_LENGTH]
