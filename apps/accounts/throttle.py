"""Failed sign-in limits: 5 failures per 15 minutes per email and IP (audit H1).

Counts live in the Django cache. Production needs a shared cache (Redis),
because the default cache is separate in each worker process.
"""

from __future__ import annotations

import hashlib

from django.conf import settings
from django.core.cache import cache
from django.http import HttpRequest

FAILURE_LIMIT = 5
WINDOW_SECONDS = 15 * 60
LOCKED_MESSAGE = "Too many failed attempts. Try again in 15 minutes."

LOGIN = "login"
SET_PASSWORD = "set-password"


def client_ip(request: HttpRequest) -> str:
    """REMOTE_ADDR, or the trusted proxy header when one is configured.

    ``TRUSTED_PROXY_IP_HEADER`` (for example ``HTTP_X_REAL_IP``) must name a
    header that the proxy always sets; a client can forge any other header.
    """
    header = getattr(settings, "TRUSTED_PROXY_IP_HEADER", "")
    if header:
        value = request.META.get(header, "").split(",")[0].strip()
        if value:
            return value
    return request.META.get("REMOTE_ADDR", "")


def _key(scope: str, identity: str, ip: str) -> str:
    raw = f"{scope}|{identity.strip().lower()}|{ip}".encode()
    return f"throttle:{scope}:{hashlib.sha256(raw).hexdigest()}"


def is_locked(scope: str, identity: str, ip: str) -> bool:
    return cache.get(_key(scope, identity, ip), 0) >= FAILURE_LIMIT


def record_failure(scope: str, identity: str, ip: str) -> None:
    key = _key(scope, identity, ip)
    cache.add(key, 0, WINDOW_SECONDS)  # the window starts at the first failure
    try:
        cache.incr(key)
    except ValueError:  # expired between add and incr
        cache.set(key, 1, WINDOW_SECONDS)


def reset(scope: str, identity: str, ip: str) -> None:
    cache.delete(_key(scope, identity, ip))
