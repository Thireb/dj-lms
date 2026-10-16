"""Roadmap 6.3: messaging rules (SPEC 4.19 and 6.5, FEATURES 11)."""

from __future__ import annotations

from datetime import timedelta

import pytest
from apps.core.roles import Role
from apps.core.tenancy import tenant_context
from apps.messaging.models import Broadcast, Draft, Message, Thread, ThreadMember
from apps.messaging.services import (
    NO_ONE_ACTIVE,
    NOT_A_MEMBER,
    NOT_REACHABLE,
    delete_forever,
    folder_members,
    mark_read,
    member_of,
    move_to_trash,
    reachable,
    reply,
    restore,
    save_draft,
    search_people,
    send_draft,
    send_message,
    set_starred,
    thread_rows,
    unread_count,
)
from django.core.exceptions import ValidationError
from django.utils import timezone

from tests.conftest import make_user
from tests.messaging.conftest import run


def _reach(school, user) -> set[str]:
    return {row.email for row in run(school, reachable, user)}


def _send(school, sender, recipient, body="Hello.", subject="Timetable", **kwargs):
    return run(school, send_message, sender, recipient, subject, body, **kwargs)


def _folder(school, user, folder) -> list[str]:
    with tenant_context(school.morning.institute):
        return [row.thread.subject for row in folder_members(user, folder)]


# Reach (SPEC 6.5)


@pytest.mark.django_db
def test_reach_by_role(school, admin) -> None:
    sub = make_user(
        email="sub-a@example.com", role=Role.SUB_ADMIN, institute=admin.institute
    )
    t1, t2 = school.teacher_1.user.email, school.teacher_2.user.email
    s1, s2 = school.student_1.user.email, school.student_2.user.email
    g1, g2 = school.guardian_1.user.email, school.guardian_2.user.email
    staff = {admin.email, sub.email}
    # Teacher 1 teaches Morning: student 1 and guardian 1, not the Evening ones.
    teacher = _reach(school, school.teacher_1.user)
    assert staff | {t2, s1, g1} <= teacher
    assert not {s2, g2, t1} & teacher
    # Student 1 is in Morning: the admins and teacher 1 only.
    assert _reach(school, school.student_1.user) == staff | {t1}
    assert _reach(school, school.guardian_1.user) == staff | {t1}
    everyone = _reach(school, admin)
    assert {sub.email, t1, t2, s1, s2, g1, g2} <= everyone
    assert school.student_b.user.email not in everyone  # another institute


@pytest.mark.django_db
def test_inactive_people_are_not_reachable(school, admin) -> None:
    user = school.student_1.user
    user.is_active = False
    user.save()
    assert user.email not in _reach(school, admin)


@pytest.mark.django_db
def test_search_finds_reachable_people_by_name_or_email(school, admin) -> None:
    found = run(school, search_people, school.student_1.user, "t1-a")
    assert [row.email for row in found] == [school.teacher_1.user.email]
    assert run(school, search_people, school.student_1.user, "s2-a") == []


# Sending and replying


@pytest.mark.django_db
def test_send_makes_a_thread_for_two(school) -> None:
    thread = _send(school, school.student_1.user, school.teacher_1.user, subject="  ")
    assert thread.subject == "(No subject)"
    # unscoped: test assertion outside a tenant context.
    members = ThreadMember.unscoped.filter(thread=thread)
    assert {m.user for m in members} == {school.student_1.user, school.teacher_1.user}
    assert Message.unscoped.get(thread=thread).body == "Hello."


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("body", "error"),
    [("   ", "Write your message."), ("x" * 5001, "5000 characters at most")],
)
def test_send_needs_a_body(school, body, error) -> None:
    with pytest.raises(ValidationError, match=error):
        _send(school, school.student_1.user, school.teacher_1.user, body=body)


@pytest.mark.django_db
def test_send_outside_reach_is_refused(school) -> None:
    for recipient in (
        school.teacher_2.user,
        school.student_2.user,
        school.teacher_b.user,
    ):
        with pytest.raises(ValidationError) as error:
            _send(school, school.student_1.user, recipient)
        assert error.value.message_dict == {"recipient": [NOT_REACHABLE]}
    assert not Thread.unscoped.exists()


@pytest.mark.django_db
def test_folders_and_unread(school) -> None:
    student, teacher = school.student_1.user, school.teacher_1.user
    thread = _send(school, student, teacher)
    assert _folder(school, student, "sent") == ["Timetable"]
    assert _folder(school, student, "inbox") == []
    assert _folder(school, teacher, "inbox") == ["Timetable"]
    assert run(school, unread_count, teacher) == 1
    assert run(school, unread_count, student) == 0
    member = run(school, member_of, teacher, thread)
    run(school, mark_read, member)
    assert run(school, unread_count, teacher) == 0
    later = timezone.now() + timedelta(minutes=1)
    run(school, reply, thread, teacher, "Thanks.", now=later)
    assert run(school, unread_count, student) == 1
    assert _folder(school, student, "inbox") == ["Timetable"]
    with tenant_context(student.institute):
        (row,) = thread_rows(student, list(folder_members(student, "inbox")))
    assert (row.last_body, row.unread, row.people) == (
        "Thanks.",
        True,
        str(teacher.get_full_name() or teacher.email),
    )


@pytest.mark.django_db
def test_star_trash_restore_and_delete_forever(school) -> None:
    student, teacher = school.student_1.user, school.teacher_1.user
    thread = _send(school, student, teacher)
    member = run(school, member_of, teacher, thread)
    run(school, set_starred, member, True)
    assert _folder(school, teacher, "starred") == ["Timetable"]
    with pytest.raises(ValidationError, match="Trash first"):
        run(school, delete_forever, member)
    run(school, move_to_trash, member)
    assert _folder(school, teacher, "inbox") == []
    assert _folder(school, teacher, "starred") == []
    assert _folder(school, teacher, "trash") == ["Timetable"]
    run(school, restore, member)
    assert _folder(school, teacher, "inbox") == ["Timetable"]
    run(school, move_to_trash, member)
    run(school, delete_forever, member)
    for folder in ("inbox", "sent", "starred", "trash"):
        assert _folder(school, teacher, folder) == [], folder
    assert _folder(school, student, "sent") == ["Timetable"]  # still theirs
    # A new message brings it back, like a new email.
    run(school, reply, thread, student, "Are you there?")
    assert _folder(school, teacher, "inbox") == ["Timetable"]


@pytest.mark.django_db
def test_reply_needs_a_member_and_an_active_other(school) -> None:
    student, teacher = school.student_1.user, school.teacher_1.user
    thread = _send(school, student, teacher)
    with pytest.raises(ValidationError, match=NOT_A_MEMBER):
        run(school, reply, thread, school.teacher_2.user, "Hi.")
    teacher.is_active = False
    teacher.save()
    with pytest.raises(ValidationError, match=NO_ONE_ACTIVE):
        run(school, reply, thread, student, "Hello again.")


# Drafts


@pytest.mark.django_db
def test_drafts_save_and_send(school) -> None:
    student, teacher = school.student_1.user, school.teacher_1.user
    draft = run(school, save_draft, student, recipient=None, subject="", body="")
    draft = run(
        school,
        save_draft,
        student,
        recipient=teacher,
        subject="Homework",
        body="Half done.",
        draft=draft,
    )
    assert Draft.unscoped.count() == 1
    with pytest.raises(ValidationError):
        run(
            school,
            save_draft,
            student,
            recipient=school.teacher_2.user,
            subject="",
            body="",
        )
    thread = run(
        school, send_draft, draft, recipient=teacher, subject="Homework", body="Done."
    )
    assert thread.subject == "Homework" and not Draft.unscoped.exists()


# Scopes


@pytest.mark.django_db
def test_scopes(school, admin, anonymous_user) -> None:
    student, teacher = school.student_1.user, school.teacher_1.user
    thread = _send(school, student, teacher)
    run(school, save_draft, student, recipient=None, subject="Mine", body="")
    assert not Thread.objects.exists()  # no tenant context
    assert not Thread.objects.for_user(anonymous_user).exists()
    with tenant_context(student.institute):
        for user, threads, members, drafts in (
            (student, 1, 1, 1),
            (teacher, 1, 1, 0),
            (school.teacher_2.user, 0, 0, 0),
            (school.guardian_1.user, 0, 0, 0),
            (admin, 1, 0, 0),  # the monitor sees threads, not drafts or states
        ):
            assert Thread.objects.for_user(user).count() == threads, user
            assert Message.objects.for_user(user).count() == threads, user
            assert ThreadMember.objects.for_user(user).count() == members, user
            assert Draft.objects.for_user(user).count() == drafts, user
            assert not Broadcast.objects.for_user(user).exists()
    with tenant_context(school.teacher_b.institute):
        assert not Thread.objects.for_user(school.teacher_b.user).exists()
    assert thread.pk
