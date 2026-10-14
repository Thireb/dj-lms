from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime

from django.utils import timezone
from django.utils.dateformat import format as date_format
from django.utils.dateparse import parse_datetime

from apps.ui.components.base import Component
from apps.ui.safe_url import safe_url


def _utc_iso(dt: datetime) -> str:
    try:
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt, UTC)
        return dt.astimezone(UTC).isoformat()
    except OverflowError:
        return ""


def scheduled_at_to_iso(value: object) -> str:
    """Return a UTC ISO 8601 string, or empty if invalid."""
    if value is None or value == "":
        return ""
    if isinstance(value, datetime):
        return _utc_iso(value)
    if isinstance(value, str):
        try:
            parsed = parse_datetime(value.strip())
        except ValueError:
            return ""
        if parsed is None:
            return ""
        return _utc_iso(parsed)
    return ""


class CountdownCard(Component):
    """ "Up next": a lecture's title, when and detail lines, a live countdown
    to ``starts_at`` and one action (for example Join).

    ``starts_at`` is validated to a UTC ISO string in ``data-scheduled-at``,
    read by ``countdownCard`` in ``static/js/app.js``. With ``refresh_url``
    the card reloads itself every 30 seconds (HTMX), so a Join state that
    changes on the server shows without a page reload.
    """

    template_name = "ui/components/countdown_card.html"

    def __init__(
        self,
        title,
        starts_at,
        when="",
        detail="",
        action=None,
        refresh_url="",
        **props,
    ):
        super().__init__(
            title=title,
            scheduled_at_iso=scheduled_at_to_iso(starts_at),
            when=when,
            detail=detail,
            action=action,
            refresh_url=safe_url(refresh_url),
            **props,
        )


class LectureRow(Component):
    """One lecture in a short list: title, when and detail, and an optional
    trailing component (a badge or a button)."""

    template_name = "ui/components/lecture_row.html"

    def __init__(self, title, when, detail="", trailing=None, **props):
        super().__init__(
            title=title, when=when, detail=detail, trailing=trailing, **props
        )


@dataclass(frozen=True)
class CalendarItem:
    """One entry in a calendar day. ``tone`` is ``info``, ``success``,
    ``neutral`` or ``danger`` (cancelled entries are struck through)."""

    time: str
    title: str
    detail: str = ""
    status: str = ""
    tone: str = "info"
    url: str | None = None


@dataclass(frozen=True)
class CalendarDay:
    day: date
    items: list[CalendarItem] = field(default_factory=list)
    is_today: bool = False
    in_month: bool = True


class Calendar(Component):
    """A week (seven day cards, side by side from lg) or a month (a grid of
    weeks from md; a list of the days that have entries on phones), with
    previous, today and next links."""

    template_name = "ui/components/calendar.html"

    def __init__(
        self,
        days,
        view="week",
        label="",
        previous_url="",
        today_url="",
        next_url="",
        empty_text="Nothing on these days.",
        empty_day_text="No lectures",
        **props,
    ):
        super().__init__(
            days=days,
            view=view,
            label=label,
            previous_url=safe_url(previous_url),
            today_url=safe_url(today_url),
            next_url=safe_url(next_url),
            empty_text=empty_text,
            empty_day_text=empty_day_text,
            **props,
        )

    def get_context(self):
        ctx = super().get_context()
        days = [_safe_day(day) for day in ctx["days"]]
        ctx["days"] = days
        ctx["weeks"] = [days[start : start + 7] for start in range(0, len(days), 7)]
        ctx["weekday_names"] = [date_format(day.day, "D") for day in days[:7]]
        ctx["busy_days"] = [day for day in days if day.items and day.in_month]
        return ctx


def _safe_day(day: CalendarDay) -> CalendarDay:
    """Unsafe item links (for example ``javascript:``) render as plain text."""
    items = [replace(item, url=safe_url(item.url) or None) for item in day.items]
    return replace(day, items=items)
