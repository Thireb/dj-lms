"""Roadmap 5.3 (part 2c): exam mode. Leaving the page or full screen is
recorded and shown to the teacher; it never changes the score (SPEC 6.8)."""

from __future__ import annotations

from datetime import timedelta

import pytest
from apps.assessments import services
from apps.assessments.models import (
    AttemptEvent,
    AttemptEventKind,
    AttemptStatus,
    Quiz,
    QuizKind,
)
from apps.assessments.services import flagged_kinds, log_attempt_event
from apps.core.roles import Role
from apps.core.tenancy import tenant_context
from django.test import Client
from django.urls import reverse

from tests.assessments.test_attempts import _make_student, _save, _start, live_quiz
from tests.conftest import cell, make_user, table_row
from tests.lectures.conftest import signed_in

LEFT_PAGE = AttemptEventKind.LEFT_PAGE
LEFT_FULL = AttemptEventKind.LEFT_FULL_SCREEN
ROLES = {
    Role.INSTITUTE_ADMIN,
    Role.SUB_ADMIN,
    Role.TEACHER,
    Role.STUDENT,
    Role.GUARDIAN,
}


def live_exam(school, **fields):
    values = {
        "kind": QuizKind.EXAM,
        "flag_tab_leaving": True,
        "require_full_screen": True,
    }
    values.update(fields)
    quiz, _ = live_quiz(school, **values)
    return quiz


def _log(attempt, kind, now=None):
    with tenant_context(attempt.institute):
        return log_attempt_event(attempt, kind, now=now)


def _kinds() -> list[str]:
    # unscoped: test assertion outside a tenant context.
    return list(AttemptEvent.unscoped.values_list("kind", flat=True))


def _event_url(quiz) -> str:
    return reverse("student:quiz_event", kwargs={"pk": quiz.pk})


# Rules


@pytest.mark.django_db
def test_only_an_exam_flags_and_only_what_it_asks(school) -> None:
    quiz, _ = live_quiz(school, title="Plain")
    assert flagged_kinds(quiz) == set()
    # A plain quiz with the flags set (the services clear them) still has none.
    # unscoped: test set-up outside a tenant context.
    Quiz.unscoped.filter(pk=quiz.pk).update(
        flag_tab_leaving=True, require_full_screen=True
    )
    quiz.refresh_from_db()
    assert flagged_kinds(quiz) == set()
    assert flagged_kinds(live_exam(school)) == {LEFT_PAGE, LEFT_FULL}
    leaving = live_exam(school, require_full_screen=False)
    assert flagged_kinds(leaving) == {LEFT_PAGE}
    full = live_exam(school, flag_tab_leaving=False)
    assert flagged_kinds(full) == {LEFT_FULL}


@pytest.mark.django_db
def test_flags_are_recorded_while_answering(school) -> None:
    exam = live_exam(school)
    attempt = _start(exam, school.student_1)
    assert _log(attempt, LEFT_PAGE) is not None
    assert _log(attempt, LEFT_FULL) is not None
    assert _kinds() == [LEFT_PAGE, LEFT_FULL]


@pytest.mark.django_db
def test_a_flag_the_exam_does_not_ask_for_is_ignored(school) -> None:
    exam = live_exam(school, require_full_screen=False)
    attempt = _start(exam, school.student_1)
    assert _log(attempt, LEFT_FULL) is None
    assert _log(attempt, "anything") is None
    quiz, _ = live_quiz(school, title="Plain")
    assert _log(_start(quiz, school.student_1), LEFT_PAGE) is None
    assert _kinds() == []


@pytest.mark.django_db
def test_no_flags_after_the_attempt_ends(school) -> None:
    exam = live_exam(school)
    attempt = _start(exam, school.student_1)
    late = attempt.deadline + timedelta(minutes=2)
    assert _log(attempt, LEFT_PAGE, now=late) is None
    # The grace minute still counts, like the answers.
    assert _log(attempt, LEFT_PAGE, now=attempt.deadline) is not None
    _save(attempt, {}, submit=True)
    assert _log(attempt, LEFT_PAGE) is None
    assert _kinds() == [LEFT_PAGE]


@pytest.mark.django_db
def test_flags_stop_at_the_cap(school, monkeypatch) -> None:
    monkeypatch.setattr(services, "MAX_EVENTS", 2)
    attempt = _start(live_exam(school), school.student_1)
    for _ in range(3):
        _log(attempt, LEFT_PAGE)
    assert len(_kinds()) == 2


@pytest.mark.django_db
def test_flags_never_change_the_score(school) -> None:
    exam = live_exam(school)
    attempt = _start(exam, school.student_1)
    _log(attempt, LEFT_PAGE)
    attempt = _save(attempt, {}, submit=True)
    assert attempt.status == AttemptStatus.SUBMITTED  # not failed or ended


@pytest.mark.django_db
def test_flag_scopes(school, institute_a, institute_b, anonymous_user) -> None:
    attempt = _start(live_exam(school), school.student_1)
    _log(attempt, LEFT_PAGE)
    admin_a = make_user(
        email="admin-a@example.com", role=Role.INSTITUTE_ADMIN, institute=institute_a
    )
    admin_b = make_user(
        email="admin-b@example.com", role=Role.INSTITUTE_ADMIN, institute=institute_b
    )
    assert not AttemptEvent.objects.exists()  # no tenant context
    assert not AttemptEvent.objects.for_user(anonymous_user).exists()
    for user, seen in (
        (school.teacher_1.user, 1),
        (school.teacher_2.user, 0),
        (admin_a, 1),
        (admin_b, 0),
        (school.student_1.user, 0),
        (school.guardian_1.user, 0),
    ):
        with tenant_context(user.institute):
            assert AttemptEvent.objects.for_user(user).count() == seen, user


# Pages


@pytest.mark.django_db
def test_event_view_records_and_answers_204(school) -> None:
    exam = live_exam(school)
    _start(exam, school.student_1)
    client = signed_in(school.student_1.user)
    assert client.get(_event_url(exam)).status_code == 405
    response = client.post(_event_url(exam), {"kind": "left_page"})
    assert response.status_code == 204
    response = client.post(_event_url(exam), {"kind": "<b>"})
    assert response.status_code == 204
    assert _kinds() == [LEFT_PAGE]


@pytest.mark.django_db
def test_event_view_needs_the_csrf_token(school) -> None:
    exam = live_exam(school)
    _start(exam, school.student_1)
    client = Client(enforce_csrf_checks=True)
    client.force_login(school.student_1.user)
    assert client.post(_event_url(exam), {"kind": "left_page"}).status_code == 403
    assert _kinds() == []


@pytest.mark.django_db
def test_event_view_without_an_attempt_records_nothing(school) -> None:
    exam = live_exam(school)
    _start(exam, _make_student(school))  # another student's attempt
    response = signed_in(school.student_1.user).post(
        _event_url(exam), {"kind": "left_page"}
    )
    assert response.status_code == 204
    assert _kinds() == []


@pytest.mark.django_db
def test_event_view_refuses_other_roles_and_students(school) -> None:
    exam = live_exam(school)
    _start(exam, school.student_1)
    for role in ROLES - {Role.STUDENT}:
        user = make_user(
            email=f"{role}@example.com", role=role, institute=school.math.institute
        )
        assert signed_in(user).post(_event_url(exam)).status_code == 403, role
    # Student 2 does not take this batch and subject.
    response = signed_in(school.student_2.user).post(
        _event_url(exam), {"kind": "left_page"}
    )
    assert response.status_code == 404
    assert _kinds() == []


@pytest.mark.django_db
def test_paper_shows_the_exam_guard(school) -> None:
    exam = live_exam(school, require_full_screen=False)
    _start(exam, school.student_1)
    client = signed_in(school.student_1.user)
    url = reverse("student:quiz_attempt", kwargs={"pk": exam.pk})
    html = client.get(url).content.decode()
    assert 'x-data="examGuard"' in html
    assert f'data-url="{_event_url(exam)}"' in html
    assert 'data-flag-leaving="1"' in html and 'data-full-screen="0"' in html
    assert 'data-form="attempt-form"' in html and 'id="attempt-form"' in html


@pytest.mark.django_db
def test_a_plain_quiz_has_no_exam_guard(school) -> None:
    quiz, _ = live_quiz(school)
    _start(quiz, school.student_1)
    client = signed_in(school.student_1.user)
    url = reverse("student:quiz_attempt", kwargs={"pk": quiz.pk})
    assert "examGuard" not in client.get(url).content.decode()
    detail = reverse("student:quiz_detail", kwargs={"pk": quiz.pk})
    assert "Exam mode" not in client.get(detail).content.decode()


@pytest.mark.django_db
def test_student_is_told_before_start(school) -> None:
    exam = live_exam(school, flag_tab_leaving=False)
    url = reverse("student:quiz_detail", kwargs={"pk": exam.pk})
    html = signed_in(school.student_1.user).get(url).content.decode()
    assert "Exam mode: leaving full screen is recorded" in html


@pytest.mark.django_db
def test_teacher_sees_the_flags(school) -> None:
    exam = live_exam(school)
    attempt = _start(exam, school.student_1)
    _log(attempt, LEFT_PAGE)
    _log(attempt, LEFT_PAGE)
    _log(attempt, LEFT_FULL)
    client = signed_in(school.teacher_1.user)
    html = client.get(reverse("teacher:quiz_detail", kwargs={"pk": exam.pk}))
    row = table_row(html.content.decode(), str(school.student_1))
    assert " ".join(cell(row, "flags")) == "Left the page 2, Left full screen 1"
    url = reverse(
        "teacher:quiz_attempt", kwargs={"pk": exam.pk, "attempt_pk": attempt.pk}
    )
    html = client.get(url).content.decode()
    assert "Exam flags" in html and "Flags do not change the score." in html
    assert html.count("Left the page") == 2


@pytest.mark.django_db
def test_a_plain_quiz_has_no_flags_column(school) -> None:
    quiz, _ = live_quiz(school)
    _start(quiz, school.student_1)
    client = signed_in(school.teacher_1.user)
    html = client.get(reverse("teacher:quiz_detail", kwargs={"pk": quiz.pk}))
    assert "cell-flags" not in html.content.decode()
