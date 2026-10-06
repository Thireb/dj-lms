"""Parse DATABASE_URL into Django DATABASES['default']."""

from __future__ import annotations

from urllib.parse import unquote, urlparse


def database_config_from_url(database_url: str) -> dict[str, str]:
    parsed = urlparse(database_url)
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": parsed.path.lstrip("/"),
        "USER": unquote(parsed.username or ""),
        "PASSWORD": unquote(parsed.password or ""),
        "HOST": parsed.hostname or "",
        "PORT": str(parsed.port or ""),
    }
