"""The one place that makes notifications (ARCHITECTURE 10, SPEC 7).

``notify`` takes the recipients, an event from ``EVENTS`` and a short text.
It leaves out users who are inactive, in another institute, or who switched
off the event's group ("class alerts" or "fee alerts", SPEC 4.22). System
notices always go.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import datetime, timedelta
from typing import Any

from django.db import models
from django.utils import timezone

from apps.core.tenancy import get_current_institute
from apps.notifications.models import Notification

RETENTION = timedelta(days=90)  # SPEC 7
PANEL_SIZE = 8  # the latest notifications in the bell
TEXT_LENGTH = 300


class Group(models.TextChoices):
    CLASS = "class", "Class alerts"
    FEE = "fee", "Fee alerts"
    SYSTEM = "system", "System notices"


# Every event of SPEC 7 and its group. Later phases hook the events of their
# own features (challans in Phase 7, homework and leave in Phase 9).
EVENTS: dict[str, str] = {
    "lecture_changed": Group.CLASS,
    "schedule_changed": Group.CLASS,
    "lecture_soon": Group.CLASS,
    "lecture_started": Group.CLASS,
    "lecture_cancelled": Group.CLASS,
    "quiz_soon": Group.CLASS,
    "challan_generated": Group.FEE,
    "challan_due": Group.FEE,
    "challan_overdue": Group.FEE,
    "receipt_submitted": Group.FEE,
    "receipt_result": Group.FEE,
    "payment_recorded": Group.FEE,
    "work_published": Group.SYSTEM,
    "homework_due": Group.SYSTEM,
    "submission_received": Group.SYSTEM,
    "work_graded": Group.SYSTEM,
    "quiz_graded": Group.SYSTEM,
    "leave_requested": Group.SYSTEM,
    "leave_result": Group.SYSTEM,
    "approval_needed": Group.SYSTEM,
    "approval_result": Group.SYSTEM,
    "new_message": Group.SYSTEM,
    "salary_slip": Group.SYSTEM,
    "portal_access": Group.SYSTEM,
}

# The user field that switches a group off.
SWITCHES = {Group.CLASS: "class_alerts", Group.FEE: "fee_alerts"}

# A link is a path in this site: "/teacher/lectures/3/", never another host.
_LINK = re.compile(r"^/(?!/)[^\s\\]*$")


def notify(
    users: Iterable[Any],
    event: str,
    text: str,
    link: str = "",
    *,
    now: datetime | None = None,
) -> int:
    """Make one notification per recipient; returns how many were made.
    Runs in the institute's tenant context."""
    if event not in EVENTS:
        raise ValueError(f"Unknown notification event: {event!r}")
    if link and not _LINK.match(link):
        raise ValueError(f"A notification link must be a path in this site: {link!r}")
    institute = get_current_institute()
    if institute is None:
        raise RuntimeError("notify needs the institute's tenant context.")
    switch = SWITCHES.get(EVENTS[event])
    now = now or timezone.now()
    text = text.strip()[:TEXT_LENGTH]
    rows, seen = [], set()
    for user in users:
        if user.pk in seen or not user.is_active or user.institute_id != institute.pk:
            continue
        if switch and not getattr(user, switch):
            continue
        seen.add(user.pk)
        rows.append(
            Notification(
                institute=institute,
                user=user,
                event=event,
                text=text,
                link=link,
                created_at=now,
            )
        )
    Notification.objects.bulk_create(rows)
    return len(rows)


def unread_count(user: Any) -> int:
    return Notification.objects.for_user(user).filter(read_at__isnull=True).count()


def latest(user: Any, limit: int = PANEL_SIZE) -> list[Notification]:
    return list(Notification.objects.for_user(user)[:limit])


def mark_read(
    user: Any, pk: int, *, now: datetime | None = None
) -> Notification | None:
    """The user's notification, marked read; None when it is not theirs."""
    row = Notification.objects.for_user(user).filter(pk=pk).first()
    if row is not None and row.read_at is None:
        row.read_at = now or timezone.now()
        row.save(update_fields=["read_at"])
    return row


def mark_all_read(user: Any, *, now: datetime | None = None) -> int:
    unread = Notification.objects.for_user(user).filter(read_at__isnull=True)
    return unread.update(read_at=now or timezone.now())


def delete_old(*, now: datetime | None = None) -> int:
    """Delete the institute's notifications older than 90 days (SPEC 7)."""
    cutoff = (now or timezone.now()) - RETENTION
    deleted, _ = Notification.objects.filter(created_at__lt=cutoff).delete()
    return deleted
