"""Read the TLS proxy setting for production (backlog S11)."""

from __future__ import annotations

import re

HEADER_NAME = re.compile(r"HTTP_[A-Z0-9_]+")


def proxy_ssl_header(header: str) -> tuple[str, str] | None:
    """``SECURE_PROXY_SSL_HEADER`` from the name of the header the TLS proxy
    always sets, for example ``HTTP_X_FORWARDED_PROTO``. Empty means no
    proxy. Django trusts this header, so the app must be reachable only
    through the proxy."""
    header = header.strip()
    if not header:
        return None
    if not HEADER_NAME.fullmatch(header):
        raise ValueError(
            "TRUSTED_PROXY_SSL_HEADER must look like HTTP_X_FORWARDED_PROTO."
        )
    return (header, "https")
