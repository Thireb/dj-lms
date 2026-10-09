"""Reject unsafe URL schemes for href, src, and HTMX URL attributes."""

from __future__ import annotations

import re
from typing import Final

_EDGE_SPACE: Final[str] = "".join(chr(c) for c in range(0x21)) + "\x7f"
_INNER_BAD: Final[re.Pattern[str]] = re.compile(r"[\x00-\x20\x7f\\]")

_BLOCKED_SCHEMES: Final[frozenset[str]] = frozenset(
    {"javascript", "data", "vbscript"},
)
_ALLOWED_SCHEMES: Final[frozenset[str]] = frozenset({"http", "https", "mailto", "tel"})


def safe_url(url: object) -> str:
    """Return a safe URL string, or ``""`` when the value must not be linked.

    Only spaces at the ends are trimmed. A URL with a space, control
    character or backslash inside is refused, not repaired, and so is a
    protocol-relative ``//host`` (audit L4).
    """
    if url is None:
        return ""
    if not isinstance(url, str):
        url = str(url)
    cleaned = url.strip(_EDGE_SPACE)
    if not cleaned or _INNER_BAD.search(cleaned):
        return ""

    if cleaned.startswith("//"):
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
