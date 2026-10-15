"""Demo assignments for seed_demo (SPEC 10): three assignments of the demo
teacher, in the batch and subject the demo student also takes.

- one open for a week, which the demo student has not answered yet;
- one due tomorrow, answered by the demo student and waiting for marks;
- one closed two days ago: the demo student's answer is graded, one other
  answer waits for marks, and the rest of the class missed it.

The services refuse a due time in the past, so the closed assignment is
made open and then moved back (still inside the tenant context).
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from apps.assessments.models import Assignment, Submission
from apps.assessments.services import (
    AssignmentDetails,
    create_assignment,
    grade_submission,
    submission_rows,
    submit_answer,
)
from apps.core.tenancy import tenant_context
from apps.institutes.models import Institute
from apps.lectures.demo import shared_link
from apps.people.demo import DEMO_STUDENT_EMAIL, DEMO_TEACHER_EMAIL
from apps.people.models import TeacherProfile

INSTRUCTIONS = (
    "Read the notes from this week's classes.\n"
    "Answer every question in full sentences and show your working."
)


def seed_assignments(institute: Institute) -> None:
    """Add the demo assignments once (a second run adds nothing)."""
    with tenant_context(institute):
        teacher = TeacherProfile.objects.filter(user__email=DEMO_TEACHER_EMAIL).first()
        if teacher is None or Assignment.objects.filter(teacher=teacher).exists():
            return
        link = shared_link(teacher)
        if link is None:
            return
        now = timezone.now()
        name = link.subject.name

        def add(title: str, days: float, marks: int) -> Assignment:
            details = AssignmentDetails(
                title=title,
                instructions=INSTRUCTIONS,
                teacher=teacher,
                batch=link.batch,
                subject=link.subject,
                total_marks=marks,
                due_at=now + timedelta(days=days),
            )
            return create_assignment(institute, details)

        add(f"{name} project", 7, 20)
        tomorrow = add(f"{name} practice sheet", 1, 10)
        closed = add(f"{name} chapter questions", 1, 10)
        _seed_answers(tomorrow, closed, teacher, now)


def _seed_answers(tomorrow, closed, teacher, now) -> None:
    students = [row.student for row in submission_rows(closed)]
    demo = next((s for s in students if s.user.email == DEMO_STUDENT_EMAIL), None)
    others = [student for student in students if student != demo]
    if demo is not None:
        submit_answer(tomorrow, demo, "Question 1: 12. Question 2: 3/4.")
        graded = submit_answer(closed, demo, "My answers are in order 1 to 5.")
        grade_submission(
            graded,
            Decimal("8.5"),
            "Good work. Check the units in question 4.",
            graded_by=teacher.user,
        )
    if others:
        submit_answer(closed, others[0], "Answers 1 to 4. I could not do 5.")
    due = now - timedelta(days=2)
    Assignment.objects.filter(pk=closed.pk).update(due_at=due)
    Submission.objects.filter(assignment=closed).update(
        submitted_at=due - timedelta(hours=3)
    )


def reset_assignments(institute: Institute) -> int:
    """Delete the institute's answers and assignments (before its people).

    Uses ``unscoped`` on purpose: a management command, one institute.
    """
    # unscoped: seed_demo --reset, limited to the demo institute.
    answers, _ = Submission.unscoped.filter(institute=institute).delete()
    # unscoped: seed_demo --reset, limited to the demo institute.
    assignments, _ = Assignment.unscoped.filter(institute=institute).delete()
    return answers + assignments
