"""Roadmap 6.1: the notification service (ARCHITECTURE 10, SPEC 7)."""

from __future__ import annotations

from datetime import timedelta

import pytest
from apps.core.tenancy import tenant_context
from apps.notifications import services
from apps.notifications.models import Notification
from apps.notifications.services import (
    EVENTS,
    Group,
    delete_old,
    latest,
    mark_all_read,
    mark_read,
    notify,
    unread_count,
)
from apps.notifications.tasks import delete_all_old_notifications
from django.utils import timezone

from tests.notifications.conftest import send


def _rows():
    # unscoped: test assertion outside a tenant context.
    return list(Notification.unscoped.order_by("pk"))


# Model and scope


@pytest.mark.django_db
def test_scopes(people, institute_a, anonymous_user) -> None:
    """Each user sees only their own notifications, admins too."""
    send(institute_a, [people["teacher"], people["student"]])
    assert not Notification.objects.exists()  # no tenant context
    assert not Notification.objects.for_user(anonymous_user).exists()
    with tenant_context(institute_a):
        assert Notification.objects.count() == 2
        for name, seen in (("teacher", 1), ("student", 1), ("admin", 0), ("other", 0)):
            assert Notification.objects.for_user(people[name]).count() == seen, name


# notify


@pytest.mark.django_db
def test_notify_makes_one_row_per_recipient(people, institute_a) -> None:
    now = timezone.now()
    made = send(
        institute_a,
        [people["teacher"], people["teacher"], people["student"]],
        event="lecture_cancelled",
        text="  Physics on Mon 3 PM is cancelled.  ",
        link="/student/lectures/",
        now=now,
    )
    assert made == 2
    row = _rows()[0]
    assert (row.institute, row.event, row.link) == (
        institute_a,
        "lecture_cancelled",
        "/student/lectures/",
    )
    assert row.text == "Physics on Mon 3 PM is cancelled."
    assert row.created_at == now and row.read_at is None


@pytest.mark.django_db
def test_notify_leaves_out_inactive_and_other_institutes(people, institute_a) -> None:
    people["student"].is_active = False
    people["student"].save()
    made = send(institute_a, [people["student"], people["other"], people["teacher"]])
    assert made == 1
    assert [row.user for row in _rows()] == [people["teacher"]]


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("switch", "event", "sent"),
    [
        ("class_alerts", "lecture_soon", False),
        ("class_alerts", "challan_due", True),
        ("fee_alerts", "challan_due", False),
        ("fee_alerts", "lecture_soon", True),
        ("class_alerts", "new_message", True),
        ("fee_alerts", "portal_access", True),
    ],
)
def test_switched_off_groups_are_not_sent(people, institute_a, switch, event, sent):
    """SPEC 7: fee and class alerts can be switched off; system notices
    always go."""
    student = people["student"]
    setattr(student, switch, False)
    student.save()
    assert send(institute_a, [student], event=event) == (1 if sent else 0)


def test_every_event_has_a_group() -> None:
    assert set(EVENTS.values()) <= set(Group.values)
    assert EVENTS["lecture_cancelled"] == Group.CLASS
    assert EVENTS["receipt_submitted"] == Group.FEE
    assert EVENTS["new_message"] == Group.SYSTEM


@pytest.mark.django_db
def test_notify_refuses_bad_input(people, institute_a) -> None:
    with pytest.raises(ValueError, match="Unknown notification event"):
        send(institute_a, [people["teacher"]], event="nothing")
    for link in (
        "https://example.com/",
        "//example.com/x",
        "javascript:alert(1)",
        "teacher/",
        "/a b/",
        "/\\example.com",
    ):
        with pytest.raises(ValueError, match="path in this site"):
            send(institute_a, [people["teacher"]], link=link)
    with pytest.raises(RuntimeError, match="tenant context"):
        notify([people["teacher"]], "new_message", "Hello.")
    assert _rows() == []


@pytest.mark.django_db
def test_long_text_is_cut(people, institute_a) -> None:
    send(institute_a, [people["teacher"]], text="x" * 400)
    assert len(_rows()[0].text) == services.TEXT_LENGTH


# Reading


@pytest.mark.django_db
def test_read_and_count(people, institute_a) -> None:
    teacher, student = people["teacher"], people["student"]
    start = timezone.now()
    for minutes in range(10):
        send(
            institute_a,
            [teacher],
            text=f"Note {minutes}",
            now=start + timedelta(minutes=minutes),
        )
    send(institute_a, [student])
    with tenant_context(institute_a):
        assert unread_count(teacher) == 10
        rows = latest(teacher)
        assert [row.text for row in rows] == [f"Note {n}" for n in range(9, 1, -1)]
        assert mark_read(teacher, rows[0].pk).is_read
        assert unread_count(teacher) == 9
        theirs = Notification.objects.get(user=student)
        assert mark_read(teacher, theirs.pk) is None  # not the teacher's
        assert mark_all_read(teacher) == 9
        assert unread_count(teacher) == 0
        assert unread_count(student) == 1


# Clean-up


@pytest.mark.django_db
def test_notifications_older_than_90_days_are_deleted(people, institute_a, institute_b):
    now = timezone.now()
    cutoff = now - services.RETENTION
    for text, at in (
        ("older", cutoff - timedelta(seconds=1)),
        ("exactly 90 days", cutoff),
        ("new", now),
    ):
        send(institute_a, [people["teacher"]], text=text, now=at)
    send(institute_b, [people["other"]], text="old in B", now=now - timedelta(days=120))
    with tenant_context(institute_a):
        assert delete_old(now=now) == 1  # only institute A, only the older one
    assert sorted(row.text for row in _rows()) == ["exactly 90 days", "new", "old in B"]


@pytest.mark.django_db
def test_the_nightly_job_covers_every_institute(people, institute_a, institute_b):
    old = timezone.now() - timedelta(days=120)
    send(institute_a, [people["teacher"]], text="old in A", now=old)
    send(institute_b, [people["other"]], text="old in B", now=old)
    send(institute_a, [people["teacher"]], text="new")
    institute_b.is_active = False
    institute_b.save()
    assert delete_all_old_notifications() == 2
    assert [row.text for row in _rows()] == ["new"]
