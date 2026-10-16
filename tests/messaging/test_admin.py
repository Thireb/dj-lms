"""Roadmap 6.3: admin Broadcast and Message Monitor (FEATURES 11), and the
demo messages (SPEC 10)."""

from __future__ import annotations

import pytest
from apps.core.roles import Role
from apps.core.tenancy import tenant_context
from apps.messaging.models import Audience, Message, Thread, ThreadMember
from apps.messaging.services import (
    broadcast_audience,
    folder_members,
    reply,
    send_broadcast,
)
from apps.messaging.views import BroadcastPage, MonitorPage
from apps.notifications.models import Notification
from django.core.exceptions import ValidationError
from django.test import RequestFactory
from django.urls import reverse

from tests.conftest import make_user
from tests.lectures.conftest import signed_in
from tests.messaging.conftest import run
from tests.messaging.test_pages import _send

BROADCAST = reverse("admin:message_broadcast")
MONITOR = reverse("admin:message_monitor")


def _broadcast(school, admin, audience=Audience.TEACHERS, **kwargs):
    return run(
        school,
        send_broadcast,
        admin,
        audience,
        "Staff meeting",
        "Friday at 2 PM.",
        **kwargs,
    )


# Broadcast


@pytest.mark.django_db
def test_a_broadcast_is_one_private_thread_each(school, admin) -> None:
    broadcast = _broadcast(school, admin)
    teachers = [school.teacher_1.user, school.teacher_2.user, school.teacher_idle.user]
    assert broadcast.recipients == len(teachers)
    # unscoped: test assertion outside a tenant context.
    threads = Thread.unscoped.filter(broadcast=broadcast)
    assert threads.count() == len(teachers)
    for thread in threads:
        assert ThreadMember.unscoped.filter(thread=thread).count() == 2
    note = Notification.unscoped.get(user=school.teacher_1.user)
    mine = ThreadMember.unscoped.get(user=school.teacher_1.user).thread_id
    assert note.link == reverse("teacher:message_thread", kwargs={"pk": mine})
    assert note.text == f"New message from {admin.email}: Staff meeting"


@pytest.mark.django_db
def test_a_reply_reaches_only_the_sender(school, admin) -> None:
    _broadcast(school, admin)
    thread = Thread.unscoped.get(members__user=school.teacher_1.user)
    run(school, reply, thread, school.teacher_1.user, "I will come.")
    assert not Notification.unscoped.filter(
        user=school.teacher_2.user, text__contains="I will"
    ).exists()
    with tenant_context(admin.institute):
        inbox = [m.thread_id for m in folder_members(admin, "inbox")]
        sent = list(folder_members(admin, "sent"))
    assert inbox == [thread.pk]
    assert sent == []  # the broadcast threads stay out of Sent


@pytest.mark.django_db
def test_audiences(school, admin) -> None:
    def emails(audience, batch=None):
        with tenant_context(admin.institute):
            return {u.email for u in broadcast_audience(admin, audience, batch)}

    assert emails(Audience.STUDENTS) == {
        school.student_1.user.email,
        school.student_2.user.email,
        school.student_new.user.email,
    }
    assert emails(Audience.GUARDIANS) == {
        school.guardian_1.user.email,
        school.guardian_2.user.email,
    }
    assert emails(Audience.BATCH, school.morning) == {
        school.student_1.user.email,
        school.guardian_1.user.email,
    }
    assert school.teacher_b.user.email not in emails(Audience.ALL)
    assert admin.email not in emails(Audience.ALL)


@pytest.mark.django_db
def test_broadcast_rules(school, admin) -> None:
    with pytest.raises(ValidationError, match="Only the institute office"):
        _broadcast(school, school.teacher_1.user)
    with pytest.raises(ValidationError) as error:
        _broadcast(school, admin, Audience.BATCH)
    assert error.value.message_dict == {"batch": ["Choose the batch."]}
    assert not Thread.unscoped.exists()


@pytest.mark.django_db
def test_broadcast_page(school, admin) -> None:
    client = signed_in(admin)
    assert client.get(BROADCAST).status_code == 200
    response = client.post(
        BROADCAST,
        {
            "audience": "batch",
            "batch": school.morning.pk,
            "subject": "Exam",
            "body": "Monday.",
        },
    )
    assert response.status_code == 302
    html = client.get(BROADCAST).content.decode()
    assert "A batch: Morning" in html and "Exam" in html


@pytest.mark.django_db
def test_sub_admin_needs_the_messages_menu(school) -> None:
    sub = make_user(
        email="sub@example.com", role=Role.SUB_ADMIN, institute=school.morning.institute
    )
    institute = school.morning.institute
    for page, path in ((BroadcastPage, BROADCAST), (MonitorPage, MONITOR)):
        request = RequestFactory().get(path)
        request.user, request.institute = sub, institute
        sub.allowed_menus = ["messages"]
        with tenant_context(institute):
            assert page.as_view()(request).status_code == 200, page
        sub.allowed_menus = ["people"]
        assert page.as_view()(request).status_code == 403, page


# Message Monitor


@pytest.mark.django_db
def test_monitor_lists_every_thread_with_filters(school, admin) -> None:
    _send(school, school.student_1.user, school.teacher_1.user, "Homework")
    _send(school, school.guardian_2.user, school.teacher_2.user, "Absence")
    client = signed_in(admin)
    html = client.get(MONITOR).content.decode()
    assert "Homework" in html and "Absence" in html
    html = client.get(MONITOR, {"q": "absence"}).content.decode()
    assert "Absence" in html and "Homework" not in html
    html = client.get(MONITOR, {"role": "guardian"}).content.decode()
    assert "Absence" in html and "Homework" not in html
    assert client.get(MONITOR, {"role": "<x>"}).status_code == 200


@pytest.mark.django_db
def test_monitor_thread_is_read_only(school, admin) -> None:
    thread = _send(school, school.student_1.user, school.teacher_1.user, "Homework")
    url = reverse("admin:message_monitor_thread", kwargs={"pk": thread.pk})
    html = signed_in(admin).get(url).content.decode()
    assert "Hello." in html and "Read only" in html and "Send reply" not in html
    teacher = ThreadMember.unscoped.get(thread=thread, user=school.teacher_1.user)
    assert teacher.last_read_at is None
    other = make_user(
        email="admin-b@example.com",
        role=Role.INSTITUTE_ADMIN,
        institute=school.teacher_b.institute,
    )
    assert signed_in(other).get(url).status_code == 404
    assert Message.unscoped.count() == 1


# Demo (SPEC 10: 30 messages across roles)


@pytest.mark.django_db
def test_demo_has_thirty_messages(settings, monkeypatch) -> None:
    from django.core.management import call_command

    monkeypatch.setenv("SEED_DEMO_PASSWORD", "demo-test-pass-123")
    settings.DEBUG = True
    call_command("seed_demo")
    call_command("seed_demo")
    assert Message.unscoped.count() == 30
    roles = set(Message.unscoped.values_list("sender__role", flat=True))
    assert {Role.INSTITUTE_ADMIN, Role.TEACHER, Role.STUDENT, Role.GUARDIAN} <= roles
    call_command("seed_demo", "--reset")
    assert not Message.unscoped.exists() and not Thread.unscoped.exists()
