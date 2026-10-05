"""Resolve and activate a user's display timezone."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.utils import timezone

if TYPE_CHECKING:
    from apps.institutes.models import Institute


def resolve_user_timezone(
    user: Any,
    *,
    institute: Institute | None = None,
) -> str:
    """Return an IANA timezone name for *user* (fallback UTC)."""
    tz_name = getattr(user, "timezone", None)
    if tz_name:
        return _valid_zone(str(tz_name))

    if institute is None:
        institute = getattr(user, "institute", None)

    if institute is not None:
        institute_tz = getattr(institute, "timezone", None)
        if institute_tz:
            return _valid_zone(str(institute_tz))

    institute_id = getattr(user, "institute_id", None)
    if institute_id is not None and institute is None:
        from apps.institutes.models import Institute

        try:
            loaded = Institute.objects.get(pk=institute_id)
        except Institute.DoesNotExist:
            pass
        else:
            if loaded.timezone:
                return _valid_zone(loaded.timezone)

    return "UTC"


def activate_timezone_for_user(
    user: Any,
    *,
    institute: Institute | None = None,
) -> str:
    """Activate Django's timezone for *user*; return the zone name used."""
    zone_name = resolve_user_timezone(user, institute=institute)
    timezone.activate(ZoneInfo(zone_name))
    return zone_name


def deactivate_timezone() -> None:
    timezone.deactivate()


def _valid_zone(name: str) -> str:
    try:
        ZoneInfo(name)
    except ZoneInfoNotFoundError:
        return "UTC"
    return name
