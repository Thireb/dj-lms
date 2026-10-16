"""Roadmap 5.4: scores on the guardian portal (backlog AS2; a guardian sees
a quiz score only after grading, SPEC 6.8) and the student's answer review
after a quiz closes (backlog AS8)."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from apps.assessments.models import AttemptStatus, QuizAttempt
from apps.core.roles import Role
from django.urls import reverse
from django.utils import timezone

from tests.assessments.conftest import add_assignment, answer, grade
from tests.assessments.test_attempts import _items, _start, live_quiz
from tests.assessments.test_quizzes import opened
from tests.assessments.test_results import _mark, _submitted
from tests.conftest import cell, make_user, table_row
from tests.lectures.conftest import signed_in

ASSIGNMENTS = reverse("guardian:assignment_list")
QUIZZES = reverse("guardian:quiz_list")


def _guardian_html(school, url) -> str:
    return signed_in(school.guardian_1.user).get(url).content.decode()


# Access


@pytest.mark.django_db
def test_other_roles_get_403(school) -> None:
    others = [school.teacher_1.user, school.student_1.user]
    for role in (Role.INSTITUTE_ADMIN, Role.SUB_ADMIN):
        others.append(
            make_user(
                email=f"{role}@example.com", role=role, institute=school.math.institute
            )
        )
    for user in others:
        client = signed_in(user)
        assert client.get(ASSIGNMENTS).status_code == 403, user.role
        assert client.get(QUIZZES).status_code == 403, user.role


@pytest.mark.django_db
def test_a_guardian_without_children_sees_the_empty_state(school) -> None:
    lonely = make_user(
        email="g9@example.com", role=Role.GUARDIAN, institute=school.math.institute
    )
    client = signed_in(lonely)
    for url in (ASSIGNMENTS, QUIZZES):
        html = client.get(url).content.decode()
        assert "No children are linked to this account yet." in html


@pytest.mark.django_db
def test_menu_links_are_built(school) -> None:
    html = _guardian_html(school, QUIZZES)
    assert f'href="{ASSIGNMENTS}"' in html and f'href="{QUIZZES}"' in html


# Assignments


@pytest.mark.django_db
def test_assignment_marks_show_once_graded(school) -> None:
    graded = add_assignment(school, title="Graded sheet")
    grade(answer(graded, school.student_1), "7.5")
    sent = add_assignment(school, title="Sent sheet")
    answer(sent, school.student_1)
    html = _guardian_html(school, ASSIGNMENTS)
    assert "Assignments of" in html and str(school.student_1) in html
    row = table_row(html, "Graded sheet")
    assert cell(row, "status") == ["Graded"]
    assert cell(row, "marks") == ["7.5", "/", "10"]
    row = table_row(html, "Sent sheet")
    assert cell(row, "status") == ["Submitted"] and cell(row, "marks") == ["-"]
    assert "cell-actions" not in row
    assert reverse("student:assignment_detail", kwargs={"pk": sent.pk}) not in html


@pytest.mark.django_db
def test_another_childs_assignments_are_not_shown(school) -> None:
    add_assignment(school, title="Morning maths")  # student 2 does not take it
    html = signed_in(school.guardian_2.user).get(ASSIGNMENTS).content.decode()
    assert "Morning maths" not in html


# Quizzes


@pytest.mark.django_db
def test_quiz_score_shows_only_once_graded(school) -> None:
    quiz, attempt = _submitted(school)
    html = _guardian_html(school, QUIZZES)
    row = table_row(html, "Fractions quiz")
    assert cell(row, "status") == ["Submitted"] and cell(row, "score") == ["-"]
    assert "cell-actions" not in row
    _mark(attempt, {_items(attempt)["Explain zero."]: Decimal(3)})
    row = table_row(_guardian_html(school, QUIZZES), "Fractions quiz")
    assert cell(row, "status") == ["Graded"]
    assert cell(row, "score") == ["5", "/", "6"]


@pytest.mark.django_db
def test_a_score_before_grading_is_not_shown(school) -> None:
    """Even a stored score stays hidden until the attempt is graded."""
    _quiz, attempt = _submitted(school)
    # unscoped: test set-up outside a tenant context.
    QuizAttempt.unscoped.filter(pk=attempt.pk).update(score=Decimal(2))
    row = table_row(_guardian_html(school, QUIZZES), "Fractions quiz")
    assert cell(row, "score") == ["-"]


@pytest.mark.django_db
def test_another_childs_quizzes_are_not_shown(school) -> None:
    _submitted(school)
    html = signed_in(school.guardian_2.user).get(QUIZZES).content.decode()
    assert "Fractions quiz" not in html


# Student answer review (AS8)


def _quiz_page(school, quiz) -> str:
    url = reverse("student:quiz_detail", kwargs={"pk": quiz.pk})
    return signed_in(school.student_1.user).get(url).content.decode()


@pytest.mark.django_db
def test_answers_show_after_the_quiz_closes(school) -> None:
    quiz, attempt = _submitted(school)
    assert "cell-right" not in _quiz_page(school, quiz)  # still live
    opened(quiz, minutes_ago=60)  # closed after 30 + 10 minutes
    html = _quiz_page(school, quiz)
    assert "cell-right" in html
    row = table_row(html, "Half of 10?")
    assert cell(row, "answer") == ["5"] and cell(row, "right") == ["2.", "5"]
    row = table_row(html, "Is 1 odd?")
    assert cell(row, "answer") == ["No"] and cell(row, "marks") == ["0", "/", "1"]
    assert cell(table_row(html, "Explain zero."), "marks") == ["-"]


@pytest.mark.django_db
def test_no_answers_while_the_attempt_is_open(school) -> None:
    """In the grace minute after the close the attempt can still be open:
    the right answers stay hidden."""
    quiz, _ = live_quiz(school)
    attempt = _start(quiz, school.student_1)
    opened(quiz, minutes_ago=41)  # closed a minute ago
    # unscoped: test set-up outside a tenant context.
    QuizAttempt.unscoped.filter(pk=attempt.pk).update(
        deadline=timezone.now() - timedelta(seconds=20)
    )
    html = _quiz_page(school, quiz)
    attempt.refresh_from_db()
    assert attempt.status == AttemptStatus.IN_PROGRESS
    assert "cell-right" not in html


@pytest.mark.django_db
def test_no_answers_without_an_attempt(school) -> None:
    quiz, _ = live_quiz(school)
    opened(quiz, minutes_ago=60)
    assert "cell-right" not in _quiz_page(school, quiz)
