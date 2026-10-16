"""Roadmap 6.3: the Messages pages (FEATURES 11): folders, a thread with
Reply, the actions, compose and drafts, and the menu badge."""

from __future__ import annotations

import pytest
from apps.messaging.models import Draft, Message, ThreadMember
from apps.notifications.models import Notification
from django.test import Client
from django.urls import reverse

from tests.lectures.conftest import signed_in
from tests.messaging.conftest import run


def _url(portal, name, **kwargs) -> str:
    return reverse(f"{portal}:message_{name}", kwargs=kwargs or None)


def _send(school, sender, recipient, subject="Timetable", body="Hello."):
    from apps.messaging.services import send_message

    return run(school, send_message, sender, recipient, subject, body)


def _member(thread, user):
    # unscoped: test assertion outside a tenant context.
    return ThreadMember.unscoped.get(thread=thread, user=user)


# Folders and the thread


@pytest.mark.django_db
def test_inbox_shows_new_messages(school) -> None:
    _send(school, school.student_1.user, school.teacher_1.user)
    html = (
        signed_in(school.teacher_1.user).get(_url("teacher", "inbox")).content.decode()
    )
    assert "Timetable" in html and "New" in html
    assert "Institute admins can read all messages." in html
    for folder in ("Inbox", "Sent", "Starred", "Drafts", "Trash"):
        assert f">{folder}<" in html, folder
    sent = signed_in(school.student_1.user).get(
        _url("student", "inbox"), {"folder": "sent"}
    )
    assert "Timetable" in sent.content.decode()


@pytest.mark.django_db
def test_thread_page_marks_read_and_takes_a_reply(school) -> None:
    student, teacher = school.student_1.user, school.teacher_1.user
    thread = _send(school, student, teacher)
    client = signed_in(teacher)
    url = _url("teacher", "thread", pk=thread.pk)
    html = client.get(url).content.decode()
    assert "Hello." in html and _member(thread, teacher).last_read_at is not None
    response = client.post(url, {"body": "See you at 4."})
    assert response.status_code == 302 and response["Location"] == url
    # unscoped: test assertion outside a tenant context.
    assert Message.unscoped.filter(thread=thread).count() == 2
    note = Notification.unscoped.filter(user=student).latest("pk")
    assert note.link == _url("student", "thread", pk=thread.pk)
    assert (
        note.text
        == f"New message from {teacher.get_full_name() or teacher.email}: Timetable"
    )


@pytest.mark.django_db
def test_people_outside_the_thread_get_404(school) -> None:
    thread = _send(school, school.student_1.user, school.teacher_1.user)
    for user, portal in (
        (school.teacher_2.user, "teacher"),
        (school.guardian_1.user, "guardian"),
        (school.teacher_b.user, "teacher"),
    ):
        client = signed_in(user)
        assert client.get(_url(portal, "thread", pk=thread.pk)).status_code == 404
        action = _url(portal, "action", pk=thread.pk) + "?do=trash"
        assert client.post(action).status_code == 404


@pytest.mark.django_db
def test_admin_reads_threads_only_through_the_monitor(school, admin) -> None:
    """The admin is not in the thread: the inbox page cannot open it."""
    thread = _send(school, school.student_1.user, school.teacher_1.user)
    client = signed_in(admin)
    assert client.get(_url("admin", "thread", pk=thread.pk)).status_code == 404
    action = _url("admin", "action", pk=thread.pk) + "?do=trash"
    assert client.post(action).status_code == 404


@pytest.mark.django_db
def test_actions(school) -> None:
    thread = _send(school, school.student_1.user, school.teacher_1.user)
    teacher = school.teacher_1.user
    client = signed_in(teacher)
    action = _url("teacher", "action", pk=thread.pk)
    assert client.get(action).status_code == 405
    client.post(action + "?do=star")
    assert _member(thread, teacher).starred
    client.post(action + "?do=delete")  # not in the trash yet: refused
    assert not _member(thread, teacher).deleted
    assert client.post(action + "?do=trash")["Location"] == _url("teacher", "inbox")
    assert _member(thread, teacher).trashed_at is not None
    client.post(action + "?do=restore")
    assert _member(thread, teacher).trashed_at is None
    client.post(action + "?do=trash")
    client.post(action + "?do=delete")
    assert _member(thread, teacher).deleted
    assert client.get(_url("teacher", "thread", pk=thread.pk)).status_code == 404
    assert client.post(action + "?do=nothing").status_code == 404


@pytest.mark.django_db
def test_actions_need_the_csrf_token(school) -> None:
    thread = _send(school, school.student_1.user, school.teacher_1.user)
    client = Client(enforce_csrf_checks=True)
    client.force_login(school.teacher_1.user)
    response = client.post(_url("teacher", "action", pk=thread.pk) + "?do=trash")
    assert response.status_code == 403


@pytest.mark.django_db
def test_text_is_escaped(school) -> None:
    thread = _send(
        school,
        school.student_1.user,
        school.teacher_1.user,
        "<b>Hi</b>",
        "<script>x</script>",
    )
    html = (
        signed_in(school.teacher_1.user)
        .get(_url("teacher", "thread", pk=thread.pk))
        .content.decode()
    )
    assert "<script>x" not in html and "&lt;script&gt;x&lt;/script&gt;" in html
    assert "<b>Hi" not in html


# Compose and drafts


@pytest.mark.django_db
def test_compose_finds_only_reachable_people(school) -> None:
    client = signed_in(school.student_1.user)
    html = client.get(
        _url("student", "compose"), {"q": "a@example.com"}
    ).content.decode()
    assert str(school.teacher_1) in html
    assert str(school.teacher_2) not in html
    # An unreachable person in ?to= is not chosen.
    to = school.teacher_2.user.pk
    html = client.get(_url("student", "compose"), {"to": to}).content.decode()
    assert "Find a person" in html


@pytest.mark.django_db
def test_compose_sends_and_notifies(school) -> None:
    student, teacher = school.student_1.user, school.teacher_1.user
    client = signed_in(student)
    response = client.post(
        _url("student", "compose") + f"?to={teacher.pk}",
        {"to": teacher.pk, "subject": "Homework", "body": "Done.", "send": "1"},
    )
    assert response.status_code == 302
    # unscoped: test assertion outside a tenant context.
    member = ThreadMember.unscoped.get(user=teacher)
    assert response["Location"] == _url("student", "thread", pk=member.thread_id)
    note = Notification.unscoped.get(user=teacher)
    assert note.event == "new_message"
    assert note.link == _url("teacher", "thread", pk=member.thread_id)


@pytest.mark.django_db
def test_compose_to_someone_out_of_reach_is_refused(school) -> None:
    client = signed_in(school.student_1.user)
    response = client.post(
        _url("student", "compose"),
        {"to": school.teacher_2.user.pk, "subject": "", "body": "Hi.", "send": "1"},
    )
    assert response.status_code == 200
    assert "You cannot send a message to this person." in response.content.decode()
    assert not ThreadMember.unscoped.exists()


@pytest.mark.django_db
def test_drafts_save_open_send_and_delete(school) -> None:
    student, teacher = school.student_1.user, school.teacher_1.user
    client = signed_in(student)
    compose = _url("student", "compose")
    response = client.post(
        compose,
        {"to": teacher.pk, "subject": "Plan", "body": "Half.", "save_draft": "1"},
    )
    assert response["Location"] == _url("student", "inbox") + "?folder=drafts"
    draft = Draft.unscoped.get()
    html = client.get(_url("student", "inbox"), {"folder": "drafts"}).content.decode()
    assert "Plan" in html
    html = client.get(compose, {"draft": draft.pk}).content.decode()
    assert 'value="Plan"' in html and "Half." in html
    # Another user cannot open or delete it.
    other = signed_in(school.student_2.user)
    assert other.get(compose, {"draft": draft.pk}).status_code == 404
    assert other.post(_url("student", "draft_delete", pk=draft.pk)).status_code == 404
    client.post(
        compose + f"?draft={draft.pk}",
        {"to": teacher.pk, "subject": "Plan", "body": "Done.", "send": "1"},
    )
    assert (
        not Draft.unscoped.exists()
        and ThreadMember.unscoped.filter(user=teacher).exists()
    )
    draft = Draft.unscoped.create(
        institute=student.institute, owner=student, updated_at=draft.updated_at
    )
    client.post(_url("student", "draft_delete", pk=draft.pk))
    assert not Draft.unscoped.exists()


# The menu badge


@pytest.mark.django_db
def test_menu_badge(school) -> None:
    _send(school, school.student_1.user, school.teacher_1.user)
    client = signed_in(school.teacher_1.user)
    home = client.get(reverse("teacher:home")).content.decode()
    assert f'hx-get="{_url("teacher", "unread")}"' in home
    badge = client.get(_url("teacher", "unread")).content.decode()
    assert ">1<" in badge and "unread" in badge
    assert (
        signed_in(school.student_1.user)
        .get(_url("student", "unread"))
        .content.decode()
        .strip()
        == ""
    )
    response = Client().get(_url("teacher", "unread"))
    assert (response.status_code, response.content) == (204, b"")
