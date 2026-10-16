"""Roadmap 6.2: assignment, quiz and portal access notifications (SPEC 7)."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from apps.assessments.models import Quiz
from apps.assessments.services import (
    publish_quiz,
    remind_upcoming_quizzes,
    unpublish_quiz,
)
from apps.assessments.tasks import remind_all_quizzes
from apps.core.tenancy import tenant_context
from apps.people.services import set_portal_blocked
from django.urls import reverse
from django.utils import timezone

from tests.assessments.conftest import add_assignment, answer, grade
from tests.assessments.test_attempts import _items, _save, _start, live_quiz
from tests.assessments.test_quizzes import ready_quiz
from tests.assessments.test_results import _mark, _submitted
from tests.notifications.test_lecture_events import inbox, texts


def events(profile) -> list[str]:
    return [event for event, _text, _link in inbox(profile)]


# Assignments


@pytest.mark.django_db
def test_a_new_assignment_reaches_the_class(school) -> None:
    assignment = add_assignment(school)
    url = reverse("student:assignment_detail", kwargs={"pk": assignment.pk})
    ((event, text, link),) = inbox(school.student_1)
    assert (event, link) == ("work_published", url)
    assert text.startswith("New assignment: Fractions worksheet (Math), due ")
    assert text.endswith(" PKT.")
    ((_, guardian_text, guardian_link),) = inbox(school.guardian_1)
    assert guardian_text == f"For {school.student_1}: {text}"
    assert guardian_link == reverse("guardian:assignment_list")
    assert inbox(school.student_2) == [] and inbox(school.teacher_1) == []


@pytest.mark.django_db
def test_the_first_answer_tells_the_teacher(school) -> None:
    assignment = add_assignment(school)
    row = answer(assignment, school.student_1)
    answer(assignment, school.student_1, "A better answer.")
    url = reverse(
        "teacher:assignment_grade",
        kwargs={"pk": assignment.pk, "submission_pk": row.pk},
    )
    assert inbox(school.teacher_1) == [
        (
            "submission_received",
            f"{school.student_1} sent an answer to Fractions worksheet.",
            url,
        )
    ]


@pytest.mark.django_db
def test_a_grade_tells_the_student_and_guardian(school) -> None:
    assignment = add_assignment(school)
    row = answer(assignment, school.student_1)
    grade(row, "7.5")
    grade(row, "8")  # a changed grade is told again
    assert texts(school.student_1)[-2:] == [
        "Fractions worksheet is graded: 7.5 / 10.",
        "Fractions worksheet is graded: 8 / 10.",
    ]
    assert texts(school.guardian_1)[-1] == (
        f"For {school.student_1}: Fractions worksheet is graded: 8 / 10."
    )


# Quizzes


@pytest.mark.django_db
def test_marks_tell_the_student_and_guardian(school) -> None:
    _quiz, attempt = _submitted(school)
    assert "quiz_graded" not in events(school.student_1)  # waits for the teacher
    assert "quiz_graded" not in events(school.guardian_1)
    _mark(attempt, {_items(attempt)["Explain zero."]: Decimal(3)})
    assert texts(school.student_1)[-1] == "Fractions quiz is graded: 5 / 6."
    assert texts(school.guardian_1)[-1] == (
        f"For {school.student_1}: Fractions quiz is graded: 5 / 6."
    )


@pytest.mark.django_db
def test_an_mcq_quiz_graded_at_submit_tells_the_guardian_only(school) -> None:
    quiz, _ = live_quiz(school, short=False)
    _save(_start(quiz, school.student_1), {}, submit=True)
    assert "quiz_graded" not in events(school.student_1)
    assert texts(school.guardian_1)[-1] == (
        f"For {school.student_1}: Fractions quiz is graded: 0 / 3."
    )


@pytest.mark.django_db
def test_opens_soon_goes_once_an_hour_before(school) -> None:
    quiz, _ = ready_quiz(school)
    with tenant_context(quiz.institute):
        publish_quiz(quiz)
    now = quiz.opens_at - timedelta(minutes=50)
    with tenant_context(quiz.institute):
        assert remind_upcoming_quizzes(quiz.opens_at - timedelta(minutes=70)) == 0
        assert remind_upcoming_quizzes(now) == 1
        assert remind_upcoming_quizzes(now) == 0
    ((event, text, link),) = [
        row for row in inbox(school.student_1) if row[0] == "quiz_soon"
    ]
    assert text.startswith("Fractions quiz opens soon, at ") and text.endswith(" PKT.")
    assert link == reverse("student:quiz_detail", kwargs={"pk": quiz.pk})
    assert "quiz_soon" not in events(school.guardian_1)


@pytest.mark.django_db
def test_drafts_get_no_reminder_and_a_new_time_is_reminded_again(school) -> None:
    quiz, _ = ready_quiz(school)
    soon = quiz.opens_at - timedelta(minutes=30)
    with tenant_context(quiz.institute):
        assert remind_upcoming_quizzes(soon) == 0  # a draft
        publish_quiz(quiz)
        assert remind_upcoming_quizzes(soon) == 1
        unpublish_quiz(quiz)
    # unscoped: test assertion outside a tenant context.
    assert Quiz.unscoped.get(pk=quiz.pk).reminded_at is None


@pytest.mark.django_db
def test_the_quiz_reminder_job(school) -> None:
    quiz, _ = ready_quiz(school)
    with tenant_context(quiz.institute):
        publish_quiz(quiz)
    # unscoped: test set-up outside a tenant context.
    Quiz.unscoped.filter(pk=quiz.pk).update(
        opens_at=timezone.now() + timedelta(minutes=30)
    )
    assert remind_all_quizzes() == 1
    assert remind_all_quizzes() == 0


# Portal access


@pytest.mark.django_db
def test_block_and_unblock_tell_the_student(school) -> None:
    student = school.student_1
    with tenant_context(student.institute):
        set_portal_blocked(student, blocked=True)
        set_portal_blocked(student, blocked=True)  # no change: nothing new
        set_portal_blocked(student, blocked=False)
    assert inbox(student) == [
        (
            "portal_access",
            "Your student portal is paused. Contact the institute office.",
            "",
        ),
        ("portal_access", "Your student portal is open again.", ""),
    ]
    assert inbox(school.guardian_1) == []
