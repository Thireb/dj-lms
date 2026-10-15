"""Helpers for assignment tests. Fake names and text only."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from apps.assessments.models import Assignment, Submission
from apps.assessments.services import (
    AssignmentDetails,
    create_assignment,
    grade_submission,
    submit_answer,
)
from apps.core.tenancy import tenant_context
from django.utils import timezone

from tests.attendance.conftest import backdate_enrolments


def in_days(days: float) -> datetime:
    return timezone.now() + timedelta(days=days)


def assignment_details(school, **fields) -> AssignmentDetails:
    """Teacher 1, Morning/Math, 10 marks, due in 3 days."""
    values = {
        "title": "Fractions worksheet",
        "instructions": "Answer all questions.\nShow your working.",
        "teacher": school.teacher_1,
        "batch": school.morning,
        "subject": school.math,
        "total_marks": 10,
        "due_at": in_days(3),
    }
    values.update(fields)
    return AssignmentDetails(**values)


def add_assignment(school, **fields) -> Assignment:
    institute = school.morning.institute
    with tenant_context(institute):
        return create_assignment(institute, assignment_details(school, **fields))


def answer(assignment: Assignment, student, text: str = "My answer.") -> Submission:
    with tenant_context(assignment.institute):
        return submit_answer(assignment, student, text)


def grade(submission: Submission, marks: str, feedback: str = "") -> Submission:
    with tenant_context(submission.institute):
        return grade_submission(submission, Decimal(marks), feedback, graded_by=None)


def close(assignment: Assignment, days_ago: float = 1) -> Assignment:
    """Move the due time into the past, which the services refuse to do."""
    # unscoped: test set-up outside a tenant context.
    Assignment.unscoped.filter(pk=assignment.pk).update(due_at=in_days(-days_ago))
    assignment.refresh_from_db()
    return assignment


@pytest.fixture
def old_school(school):
    """The school with enrolments 60 days old, so a closed assignment still
    has its students."""
    backdate_enrolments()
    return school
