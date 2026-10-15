"""Roadmap 5.3 (part 2b): the teacher's results and the marks of short
answers (SPEC 6.8), the Attempts column, and the pages."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from apps.assessments.models import AttemptAnswer, AttemptStatus, QuizAttempt
from apps.assessments.services import (
    MARK_OPEN_MESSAGE,
    mark_attempt,
    quiz_counts,
    quiz_results,
)
from apps.core.roles import Role
from apps.core.tenancy import tenant_context
from apps.people.models import ProfileStatus, StudentProfile
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from tests.assessments.test_attempts import (
    _items,
    _make_student,
    _option,
    _save,
    _start,
    live_quiz,
)
from tests.assessments.test_quizzes import add_quiz, opened
from tests.conftest import cell, make_user, table_row
from tests.lectures.conftest import signed_in

ROLES = {
    Role.INSTITUTE_ADMIN,
    Role.SUB_ADMIN,
    Role.TEACHER,
    Role.STUDENT,
    Role.GUARDIAN,
}


def _submitted(school, *, short_answer: str = "Zero is nothing.", **fields):
    """Student 1 answers Half of 10 right (2), Is 1 odd wrong (0) and the
    short answer, and submits."""
    quiz, questions = live_quiz(school, **fields)
    attempt = _start(quiz, school.student_1)
    items = _items(attempt)
    answers = {
        items["Half of 10?"]: _option(questions[0], "5"),
        items["Is 1 odd?"]: _option(questions[1], "No"),
    }
    if short_answer:
        answers[items["Explain zero."]] = short_answer
    return quiz, _save(attempt, answers, submit=True)


def _mark(attempt, marks):
    with tenant_context(attempt.institute):
        return mark_attempt(attempt, marks)


def _detail(quiz) -> str:
    return reverse("teacher:quiz_detail", kwargs={"pk": quiz.pk})


def _attempt_url(quiz, attempt) -> str:
    return reverse(
        "teacher:quiz_attempt", kwargs={"pk": quiz.pk, "attempt_pk": attempt.pk}
    )


# Marking


@pytest.mark.django_db
def test_marks_grade_the_attempt_with_every_answer(school) -> None:
    quiz, attempt = _submitted(school)
    assert attempt.status == AttemptStatus.SUBMITTED and attempt.score is None
    short = _items(attempt)["Explain zero."]
    graded = _mark(attempt, {short: Decimal("2.5")})
    assert graded.status == AttemptStatus.GRADED
    assert graded.score == Decimal("4.5")  # 2 + 0 + 2.5
    # The marks can change later.
    assert _mark(attempt, {short: Decimal(3)}).score == Decimal(5)


@pytest.mark.django_db
@pytest.mark.parametrize("marks", [None, Decimal(-1), Decimal("3.5")])
def test_marks_must_be_zero_to_the_question_marks(school, marks) -> None:
    _quiz, attempt = _submitted(school)
    short = _items(attempt)["Explain zero."]
    with pytest.raises(ValidationError) as error:
        _mark(attempt, {} if marks is None else {short: marks})
    assert error.value.messages == ["Question 3: give 0 to 3 marks."]
    attempt.refresh_from_db()
    assert attempt.status == AttemptStatus.SUBMITTED


@pytest.mark.django_db
def test_full_and_zero_marks_are_allowed(school) -> None:
    _quiz, attempt = _submitted(school)
    short = _items(attempt)["Explain zero."]
    assert _mark(attempt, {short: Decimal(3)}).score == Decimal(5)
    assert _mark(attempt, {short: Decimal(0)}).score == Decimal(2)


@pytest.mark.django_db
def test_an_open_attempt_cannot_be_marked(school) -> None:
    quiz, _ = live_quiz(school)
    attempt = _start(quiz, school.student_1)
    with pytest.raises(ValidationError) as error:
        _mark(attempt, {_items(attempt)["Explain zero."]: Decimal(1)})
    assert error.value.messages == [MARK_OPEN_MESSAGE]


@pytest.mark.django_db
def test_an_empty_short_answer_gets_marks(school) -> None:
    _quiz, attempt = _submitted(school, short_answer="")
    short = _items(attempt)["Explain zero."]
    assert _mark(attempt, {short: Decimal(0)}).score == Decimal(2)
    # unscoped: test assertion outside a tenant context.
    row = AttemptAnswer.unscoped.get(attempt=attempt, item_id=short)
    assert row.text == "" and row.marks == 0


# Results and counts


@pytest.mark.django_db
def test_results_list_the_students_and_close_expired_attempts(school) -> None:
    quiz, _ = live_quiz(school)
    other = _make_student(school)
    attempt = _start(quiz, school.student_1)
    later = attempt.deadline + timedelta(minutes=2)
    with tenant_context(quiz.institute):
        rows = quiz_results(quiz, now=later)
    by_student = {row.student.pk: row.attempt for row in rows}
    assert set(by_student) == {school.student_1.pk, other.pk}
    assert by_student[other.pk] is None
    closed = by_student[school.student_1.pk]
    assert closed.status == AttemptStatus.SUBMITTED and closed.auto_submitted
    # An inactive student without an attempt is left out.
    # unscoped: test set-up outside a tenant context.
    StudentProfile.unscoped.filter(pk=other.pk).update(status=ProfileStatus.INACTIVE)
    with tenant_context(quiz.institute):
        assert [row.student.pk for row in quiz_results(quiz)] == [school.student_1.pk]


@pytest.mark.django_db
def test_counts_attempts_and_the_ones_to_mark(school) -> None:
    quiz, attempt = _submitted(school)
    _mark(attempt, {_items(attempt)["Explain zero."]: Decimal(1)})
    _save(_start(quiz, _make_student(school)), {}, submit=True)
    empty = add_quiz(school, title="Empty")
    with tenant_context(quiz.institute):
        counts = quiz_counts([quiz, empty])
    assert (counts[quiz.pk].attempts, counts[quiz.pk].to_mark) == (2, 1)
    assert counts[quiz.pk].total == 2
    assert (counts[empty.pk].attempts, counts[empty.pk].total) == (0, 2)


# Pages


@pytest.mark.django_db
def test_list_shows_attempts_and_to_mark(school) -> None:
    _submitted(school)
    html = signed_in(school.teacher_1.user).get(reverse("teacher:quiz_list"))
    row = table_row(html.content.decode(), "Fractions quiz")
    assert cell(row, "attempts") == ["1", "/", "1"]
    assert cell(row, "status") == ["Live", "1", "to", "mark"]


@pytest.mark.django_db
def test_quiz_page_shows_results_once_opened(school) -> None:
    client = signed_in(school.teacher_1.user)
    draft = add_quiz(school, title="Draft")
    assert "Results" not in client.get(_detail(draft)).content.decode()
    quiz, attempt = _submitted(school)
    other = _make_student(school)
    html = client.get(_detail(quiz)).content.decode()
    row = table_row(html, str(school.student_1))
    assert cell(row, "status") == ["Submitted"]
    assert cell(row, "score") == ["-"]
    assert f'href="{_attempt_url(quiz, attempt)}"' in row
    assert "Mark:" in row
    assert cell(table_row(html, str(other)), "status") == ["Not", "started"]
    opened(quiz, minutes_ago=60)  # closed after 30 + 10 minutes
    html = client.get(_detail(quiz)).content.decode()
    assert cell(table_row(html, str(other)), "status") == ["Not", "taken"]


@pytest.mark.django_db
def test_attempt_page_marks_the_short_answers(school) -> None:
    quiz, attempt = _submitted(school)
    url = _attempt_url(quiz, attempt)
    client = signed_in(school.teacher_1.user)
    html = client.get(url).content.decode()
    assert cell(table_row(html, "Half of 10?"), "answer") == ["5"]
    assert cell(table_row(html, "Half of 10?"), "marks") == ["2", "/", "2"]
    assert cell(table_row(html, "Is 1 odd?"), "marks") == ["0", "/", "1"]
    assert cell(table_row(html, "Explain zero."), "answer") == [
        "Zero",
        "is",
        "nothing.",
    ]
    short = _items(attempt)["Explain zero."]
    assert f'name="marks_{short}"' in html
    response = client.post(url, {f"marks_{short}": "4"})
    assert response.status_code == 200
    assert "Ensure this value is less than or equal to 3." in response.content.decode()
    response = client.post(url, {f"marks_{short}": "1.5"})
    assert response.status_code == 302
    assert response["Location"] == _detail(quiz)
    attempt.refresh_from_db()
    assert attempt.status == AttemptStatus.GRADED and attempt.score == Decimal("3.5")
    html = client.get(url).content.decode()
    assert f'name="marks_{short}" value="1.5"' in html  # the marks can change


@pytest.mark.django_db
def test_attempt_page_of_an_mcq_only_quiz_has_no_form(school) -> None:
    quiz, _ = live_quiz(school, short=False)
    attempt = _save(_start(quiz, school.student_1), {}, submit=True)
    html = signed_in(school.teacher_1.user).get(_attempt_url(quiz, attempt))
    html = html.content.decode()
    assert "Marks for written answers" not in html
    assert cell(table_row(html, "Half of 10?"), "answer") == ["No", "answer"]


@pytest.mark.django_db
def test_open_attempt_shows_no_answers_and_refuses_marks(school) -> None:
    quiz, _ = live_quiz(school)
    attempt = _start(quiz, school.student_1)
    url = _attempt_url(quiz, attempt)
    client = signed_in(school.teacher_1.user)
    html = client.get(url).content.decode()
    assert MARK_OPEN_MESSAGE in html and "Marks for written answers" not in html
    short = _items(attempt)["Explain zero."]
    response = client.post(url, {f"marks_{short}": "1"})
    assert response.status_code == 302
    attempt.refresh_from_db()
    assert attempt.status == AttemptStatus.IN_PROGRESS


@pytest.mark.django_db
def test_attempt_page_closes_an_expired_attempt(school) -> None:
    quiz, _ = live_quiz(school)
    attempt = _start(quiz, school.student_1)
    # unscoped: test set-up outside a tenant context.
    QuizAttempt.unscoped.filter(pk=attempt.pk).update(
        deadline=timezone.now() - timedelta(minutes=2)
    )
    html = signed_in(school.teacher_1.user).get(_attempt_url(quiz, attempt))
    assert "Marks for written answers" in html.content.decode()
    attempt.refresh_from_db()
    assert attempt.status == AttemptStatus.SUBMITTED and attempt.auto_submitted


@pytest.mark.django_db
def test_attempt_page_refuses_other_roles(school) -> None:
    quiz, attempt = _submitted(school)
    url = _attempt_url(quiz, attempt)
    for role in ROLES - {Role.TEACHER}:
        user = make_user(
            email=f"{role}@example.com", role=role, institute=school.math.institute
        )
        client = signed_in(user)
        assert client.get(url).status_code == 403, role
        assert client.post(url).status_code == 403, role


@pytest.mark.django_db
def test_other_teachers_and_quizzes_get_404(school) -> None:
    quiz, attempt = _submitted(school)
    url = _attempt_url(quiz, attempt)
    for user in (school.teacher_2.user, school.teacher_b.user):
        assert signed_in(user).get(url).status_code == 404
    # The attempt must belong to the quiz in the URL.
    other = opened(add_quiz(school, title="Other"))
    client = signed_in(school.teacher_1.user)
    assert client.get(_attempt_url(other, attempt)).status_code == 404
