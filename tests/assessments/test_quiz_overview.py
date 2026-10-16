"""Roadmap 5.3 (part 2d): the admin "Quizzes and exams" overview (SPEC 3)
and the read-only quiz page with its results."""

from __future__ import annotations

import pytest
from apps.assessments.models import QuizKind
from apps.assessments.views import AdminQuizListPage, AdminQuizPage
from apps.core.roles import Role
from apps.core.tenancy import tenant_context
from django.test import RequestFactory
from django.urls import reverse

from tests.assessments.test_attempts import _save, _start, live_quiz
from tests.assessments.test_exam_mode import live_exam
from tests.assessments.test_quizzes import add_quiz
from tests.conftest import cell, make_user, table_row
from tests.lectures.conftest import signed_in
from tests.school import link_teacher

LIST_URL = reverse("admin:quiz_list")


def _detail(quiz) -> str:
    return reverse("admin:quiz_detail", kwargs={"pk": quiz.pk})


def _admin(school, email="admin@example.com", role=Role.INSTITUTE_ADMIN):
    return make_user(email=email, role=role, institute=school.math.institute)


# Access


@pytest.mark.django_db
def test_sub_admin_needs_the_academic_menu(school) -> None:
    quiz = add_quiz(school)
    user = _admin(school, "sub@example.com", Role.SUB_ADMIN)
    institute = school.math.institute
    for page, path, kwargs in (
        (AdminQuizListPage, LIST_URL, {}),
        (AdminQuizPage, _detail(quiz), {"pk": quiz.pk}),
    ):
        request = RequestFactory().get(path)
        request.user, request.institute = user, institute
        user.allowed_menus = ["academic"]
        with tenant_context(institute):
            allowed = page.as_view()(request, **kwargs)
        user.allowed_menus = ["people"]
        denied = page.as_view()(request, **kwargs)
        assert allowed.status_code == 200, page
        assert denied.status_code == 403, page


@pytest.mark.django_db
def test_other_roles_get_403(school) -> None:
    quiz = add_quiz(school)
    users = [school.teacher_1.user, school.student_1.user, school.guardian_1.user]
    users.append(_admin(school, "sub@example.com", Role.SUB_ADMIN))  # no menus
    for user in users:
        client = signed_in(user)
        assert client.get(LIST_URL).status_code == 403, user.role
        assert client.get(_detail(quiz)).status_code == 403, user.role


@pytest.mark.django_db
def test_other_institute_sees_nothing(school) -> None:
    quiz = add_quiz(school)
    other = make_user(
        email="admin-b@example.com",
        role=Role.INSTITUTE_ADMIN,
        institute=school.teacher_b.institute,
    )
    client = signed_in(other)
    assert client.get(_detail(quiz)).status_code == 404
    assert "No quizzes yet." in client.get(LIST_URL).content.decode()


# List


@pytest.mark.django_db
def test_list_shows_every_teachers_quizzes(school) -> None:
    link_teacher(school.teacher_2, {school.evening: [school.physics, school.math]})
    quiz, _ = live_quiz(school)
    _save(_start(quiz, school.student_1), {}, submit=True)
    add_quiz(
        school,
        title="Evening exam",
        kind=QuizKind.EXAM,
        teacher=school.teacher_2,
        batch=school.evening,
    )
    client = signed_in(_admin(school))
    html = client.get(LIST_URL).content.decode()
    assert "Add quiz" not in html
    row = table_row(html, "Fractions quiz")
    assert cell(row, "teacher") == str(school.teacher_1).split()
    assert cell(row, "attempts") == ["1", "/", "1"]
    assert cell(row, "status") == ["Live", "1", "to", "mark"]
    assert f'href="{_detail(quiz)}"' in row and "View results" in row
    exam = table_row(html, "Evening exam")
    assert cell(exam, "teacher") == str(school.teacher_2).split()
    assert cell(exam, "status") == ["Draft"]
    html = client.get(LIST_URL, {"kind": "exam"}).content.decode()
    assert "Evening exam" in html and "Fractions quiz" not in html
    html = client.get(LIST_URL, {"status": "live"}).content.decode()
    assert "Fractions quiz" in html and "Evening exam" not in html


@pytest.mark.django_db
def test_list_empty_state(school) -> None:
    html = signed_in(_admin(school)).get(LIST_URL).content.decode()
    assert "Quizzes and exams show here when teachers add them." in html
    assert f'href="{LIST_URL}"' in html  # the menu item is a link now


# Quiz page


@pytest.mark.django_db
def test_draft_shows_questions_without_results(school) -> None:
    quiz = add_quiz(school)
    html = signed_in(_admin(school)).get(_detail(quiz)).content.decode()
    assert "Draft: students do not see it yet." in html
    assert "Questions" in html and "Results" not in html
    assert reverse("teacher:quiz_edit", kwargs={"pk": quiz.pk}) not in html
    assert "Publish" not in html


@pytest.mark.django_db
def test_opened_quiz_shows_results_read_only(school) -> None:
    exam = live_exam(school)
    attempt = _save(_start(exam, school.student_1), {}, submit=True)
    html = signed_in(_admin(school)).get(_detail(exam)).content.decode()
    row = table_row(html, str(school.student_1))
    assert cell(row, "status") == ["Submitted"]
    assert cell(row, "flags") == ["None"]
    assert "cell-actions" not in row
    attempt_url = reverse(
        "teacher:quiz_attempt", kwargs={"pk": exam.pk, "attempt_pk": attempt.pk}
    )
    assert attempt_url not in html
    assert str(school.teacher_1) in html  # Details: Teacher
    assert "Remove" not in html and "Add from bank" not in html
