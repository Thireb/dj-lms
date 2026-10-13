"""Lecture times in the viewer's time zone (UI-GUIDELINES: "3:00 PM PKT").

The time zone middleware activates the viewer's zone for each request.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from django.utils import timezone
from django.utils.dateformat import format as date_format


def local_date(value: datetime) -> str:
    """Example: Mon 14 Oct 2026."""
    return date_format(timezone.localtime(value), "D j M Y")


def local_time(value: datetime) -> str:
    """Example: 3:00 PM PKT."""
    return date_format(timezone.localtime(value), "g:i A T")


def time_range(starts_at: datetime, ends_at: datetime) -> str:
    """Example: 3:00 PM to 4:30 PM PKT."""
    start = date_format(timezone.localtime(starts_at), "g:i A")
    return f"{start} to {local_time(ends_at)}"


def combine_local(day: date, at: time) -> datetime:
    """A date and a wall-clock time in the viewer's zone, as an aware datetime."""
    return timezone.make_aware(datetime.combine(day, at))


def local_day_bounds(now: datetime) -> tuple[datetime, datetime]:
    """Start of the viewer's today and start of tomorrow."""
    today = timezone.localtime(now).date()
    return (
        combine_local(today, time.min),
        combine_local(today + timedelta(days=1), time.min),
    )
