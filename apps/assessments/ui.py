"""Assignment badges, tables and cards (roadmap 5.1, SPEC 2 and 3)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from django import forms
from django.urls import reverse
from django.utils import timezone

from apps.assessments.models import Assignment, SubmissionStatus
from apps.assessments.services import (
    AssignmentCount,
    StudentAssignment,
    SubmissionRow,
    is_open,
    marks_text,
)
from apps.lectures.times import local_date, local_time
from apps.ui.components.actions import IconButton
from apps.ui.components.block_stack import ButtonRow
from apps.ui.components.data import (
    Badge,
    BadgeNote,
    Column,
    DataTable,
    PersonCell,
)
from apps.ui.components.forms import CrispyForm, PortalPostForm
from apps.ui.components.layout import SectionCard

# SPEC 2: amber, blue, green, red.
STATUS_TONES = {
    SubmissionStatus.PENDING: "warning",
    SubmissionStatus.SUBMITTED: "info",
    SubmissionStatus.GRADED: "success",
    SubmissionStatus.MISSED: "danger",
}


def submission_badge(status: str) -> Badge:
    return Badge(SubmissionStatus(status).label, tone=STATUS_TONES[status])


def when(value: datetime | None) -> str:
    """Example: Mon 14 Oct 2026, 11:59 PM PKT."""
    if value is None:
        return ""
    return f"{local_date(value)}, {local_time(value)}"


def due_text(assignment: Assignment) -> str:
    return when(assignment.due_at)


def open_badge(assignment: Assignment, now: datetime) -> Badge:
    """The teacher's status: answers are taken (Open) or not (Closed)."""
    if is_open(assignment, now):
        return Badge("Open", tone="info")
    return Badge("Closed", tone="neutral")


def assignment_url(portal: str, action: str, assignment: Assignment) -> str:
    return reverse(f"{portal}:assignment_{action}", kwargs={"pk": assignment.pk})


def submitted_total(count: AssignmentCount | None) -> str:
    """Teacher list "Submitted / Total"."""
    if count is None:
        return "0 / 0"
    return f"{count.submitted} / {count.total}"


class TeacherAssignmentTable(DataTable):
    """Teacher "Assignments" (SPEC 3): Title, Batch, Due, Submitted / Total,
    Status; a row opens the answers to grade."""

    empty_title = "No assignments match these filters."

    def __init__(
        self,
        rows: list[Assignment],
        *,
        counts: dict[int, AssignmentCount] | None = None,
        now: datetime | None = None,
        **props,
    ):
        self.counts = counts or {}
        self.now = now or timezone.now()
        super().__init__(rows=rows, **props)

    @property
    def columns(self) -> list[Column]:  # type: ignore[override]
        return [
            Column("title", "Assignment"),
            Column("batch", "Batch", lambda row: row.batch.name),
            Column("subject", "Subject", lambda row: row.subject.name),
            Column("due", "Due", due_text),
            Column("submitted", "Submitted / Total", self.submitted_total),
            Column("status", "Status", self.status),
            Column("actions", "", self.actions),
        ]

    def submitted_total(self, assignment: Assignment) -> str:
        return submitted_total(self.counts.get(assignment.pk))

    def status(self, assignment: Assignment) -> Any:
        badge = open_badge(assignment, self.now)
        count = self.counts.get(assignment.pk)
        if count is None or not count.to_grade:
            return badge
        return BadgeNote(badge, f"{count.to_grade} to grade")

    def actions(self, assignment: Assignment) -> ButtonRow:
        title = assignment.title
        return ButtonRow(
            items=[
                IconButton(
                    "eye",
                    f"Open {title}",
                    url=assignment_url("teacher", "detail", assignment),
                ),
                IconButton(
                    "square-pen",
                    f"Edit {title}",
                    url=assignment_url("teacher", "edit", assignment),
                ),
            ]
        )


class SubmissionTable(DataTable):
    """The answers to one assignment, on the teacher's assignment page."""

    empty_title = "No students take this batch and subject."

    def __init__(self, rows: list[SubmissionRow], *, assignment: Assignment, **props):
        self.assignment = assignment
        super().__init__(rows=rows, **props)

    @property
    def columns(self) -> list[Column]:  # type: ignore[override]
        return [
            Column(
                "student",
                "Student",
                lambda row: PersonCell(
                    str(row.student), detail=row.student.student_code
                ),
            ),
            Column("status", "Status", lambda row: submission_badge(row.status)),
            Column("submitted", "Submitted on", self.submitted_on),
            Column("marks", "Marks", self.marks),
            Column("actions", "", self.grade_button),
        ]

    def submitted_on(self, row: SubmissionRow) -> str:
        return when(row.submission.submitted_at) if row.submission else "-"

    def marks(self, row: SubmissionRow) -> str:
        marks = row.submission.marks if row.submission else None
        return marks_text(marks, self.assignment.total_marks)

    def grade_button(self, row: SubmissionRow) -> Any:
        if row.submission is None:
            return ""
        label = "Change grade" if row.submission.is_graded else "Grade"
        url = reverse(
            "teacher:assignment_grade",
            kwargs={"pk": self.assignment.pk, "submission_pk": row.submission.pk},
        )
        return IconButton("square-pen", f"{label}: {row.student}", url=url)


class StudentAssignmentTable(DataTable):
    """Student "Assignments" (SPEC 3): Title, Subject, Due, Status, Marks."""

    empty_title = "No assignments match these filters."
    portal = "student"

    def __init__(self, rows: list[StudentAssignment], **props):
        super().__init__(rows=rows, **props)

    @property
    def columns(self) -> list[Column]:  # type: ignore[override]
        return [
            Column("title", "Assignment", lambda row: row.assignment.title),
            Column("subject", "Subject", lambda row: row.assignment.subject.name),
            Column("due", "Due", lambda row: due_text(row.assignment)),
            Column("status", "Status", lambda row: submission_badge(row.status)),
            Column("marks", "Marks", self.marks),
            Column("actions", "", self.open_button),
        ]

    def marks(self, row: StudentAssignment) -> str:
        marks = row.submission.marks if row.submission else None
        return marks_text(marks, row.assignment.total_marks)

    def open_button(self, row: StudentAssignment) -> IconButton:
        url = assignment_url(self.portal, "detail", row.assignment)
        return IconButton("eye", f"Open {row.assignment.title}", url=url)


def assignment_detail_rows(
    assignment: Assignment, *, show_teacher: bool
) -> list[tuple[str, Any]]:
    rows: list[tuple[str, Any]] = [
        ("Batch", assignment.batch.name),
        ("Subject", assignment.subject.name),
        ("Due", due_text(assignment)),
        ("Total marks", str(assignment.total_marks)),
    ]
    if show_teacher:
        rows.insert(2, ("Teacher", str(assignment.teacher)))
    return rows


def form_card(title: str, form: forms.Form, action: str, icon: str) -> SectionCard:
    """A form inside a card on a detail page."""
    form.helper.disable_csrf = True  # PortalPostForm adds the token
    return SectionCard(
        title=title,
        icon=icon,
        body=PortalPostForm(action=action, body=CrispyForm(form=form), framed=False),
    )
