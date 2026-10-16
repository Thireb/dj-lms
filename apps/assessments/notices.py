"""Assignment and quiz notifications (roadmap 6.2, SPEC 7). The services
call these inside their transaction. Times in the texts are each
recipient's local time."""

from __future__ import annotations

from typing import Any

from django.urls import reverse

from apps.assessments.models import Assignment, Quiz, QuizAttempt, Submission
from apps.lectures.times import local_date, local_time
from apps.notifications.audience import class_students, send_to_students
from apps.notifications.services import notify


def _students_of(row: Assignment | Quiz):
    return class_students(row.batch_id, [row.subject_id])


def assignment_published(assignment: Assignment) -> None:
    """SPEC 7: to the students and guardians of the batch and subject."""

    def text(user: Any) -> str:
        due = assignment.due_at
        return (
            f"New assignment: {assignment.title} ({assignment.subject.name}), "
            f"due {local_date(due)} at {local_time(due)}."
        )

    send_to_students(
        "work_published",
        _students_of(assignment),
        text,
        student_url=reverse("student:assignment_detail", kwargs={"pk": assignment.pk}),
        guardian_url=reverse("guardian:assignment_list"),
    )


def answer_received(submission: Submission) -> None:
    """SPEC 7 "submission received": the first answer only, to the teacher."""
    assignment = submission.assignment
    url = reverse(
        "teacher:assignment_grade",
        kwargs={"pk": assignment.pk, "submission_pk": submission.pk},
    )
    text = f"{submission.student} sent an answer to {assignment.title}."
    notify([assignment.teacher.user], "submission_received", text, url)


def answer_graded(submission: Submission, marks: str) -> None:
    """SPEC 7 "graded": the student and their guardians, with the marks."""
    assignment = submission.assignment
    send_to_students(
        "work_graded",
        [submission.student],
        f"{assignment.title} is graded: {marks}.",
        student_url=reverse("student:assignment_detail", kwargs={"pk": assignment.pk}),
        guardian_url=reverse("guardian:assignment_list"),
    )


def quiz_soon(quiz: Quiz) -> None:
    """SPEC 7 "quiz opens soon": the students, 1 hour before (assumed)."""

    def text(user: Any) -> str:
        return f"{quiz.title} opens soon, at {local_time(quiz.opens_at)}."

    send_to_students(
        "quiz_soon",
        _students_of(quiz),
        text,
        student_url=reverse("student:quiz_detail", kwargs={"pk": quiz.pk}),
    )


def quiz_graded(attempt: QuizAttempt, score: str, *, to_student: bool = True) -> None:
    """SPEC 7 "quiz graded": the student and their guardians. An MCQ-only
    quiz is graded at submit, where the student sees the score at once, so
    only the guardians are told (``to_student=False``)."""
    quiz = attempt.quiz
    send_to_students(
        "quiz_graded",
        [attempt.student],
        f"{quiz.title} is graded: {score}.",
        student_url=reverse("student:quiz_detail", kwargs={"pk": quiz.pk}),
        guardian_url=reverse("guardian:quiz_list"),
        to_students=to_student,
    )
