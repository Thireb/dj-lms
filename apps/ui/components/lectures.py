from __future__ import annotations

from datetime import UTC, datetime

from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.ui.components.base import Component
from apps.ui.safe_url import safe_url


def _utc_iso(dt: datetime) -> str:
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, UTC)
    return dt.astimezone(UTC).isoformat()


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
    template_name = "ui/components/countdown_card.html"

    def __init__(self, lecture, viewer, **props):
        scheduled_raw = getattr(lecture, "scheduled_at", "")
        super().__init__(
            lecture=lecture,
            viewer=viewer,
            title=getattr(lecture, "title", ""),
            scheduled_at_iso=scheduled_at_to_iso(scheduled_raw),
            meeting_link=safe_url(getattr(lecture, "meeting_link", "")),
            **props,
        )


class LectureRow(Component):
    template_name = "ui/components/lecture_row.html"

    def __init__(self, lecture, viewer, **props):
        super().__init__(lecture=lecture, viewer=viewer, **props)


class ScheduleList(Component):
    template_name = "ui/components/schedule_list.html"

    def __init__(self, lectures, viewer, **props):
        super().__init__(lectures=lectures, viewer=viewer, **props)
