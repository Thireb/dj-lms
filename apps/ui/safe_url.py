"""Reject unsafe URL schemes for href, src, and HTMX URL attributes."""

from __future__ import annotations

import re
from typing import Final

_CONTROL_AND_SPACE: Final[re.Pattern[str]] = re.compile(r"[\x00-\x1f\x7f\s]+")

_BLOCKED_SCHEMES: Final[frozenset[str]] = frozenset(
    {"javascript", "data", "vbscript"},
)
_ALLOWED_SCHEMES: Final[frozenset[str]] = frozenset({"http", "https", "mailto", "tel"})


def safe_url(url: object) -> str:
    """Return a safe URL string, or ``""`` when the value must not be linked."""
    if url is None:
        return ""
    if not isinstance(url, str):
        url = str(url)
    cleaned = _CONTROL_AND_SPACE.sub("", url)
    if not cleaned:
        return ""

    if cleaned.startswith(("/", "./", "../", "?", "#")):
        return cleaned

    colon = cleaned.find(":")
    if colon == -1:
        return ""

    scheme = cleaned[:colon].lower()
    if scheme in _BLOCKED_SCHEMES:
        return ""
    if scheme in _ALLOWED_SCHEMES:
        return cleaned
    return ""
