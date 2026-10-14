"""Attendance badges and tables (roadmap 4.1 to 4.3, SPEC 6.3)."""

from __future__ import annotations

from decimal import Decimal
from urllib.parse import urlencode

from django.urls import reverse

from apps.attendance.models import AttendanceStatus
from apps.attendance.services import (
    GroupSummary,
    LectureCount,
    Record,
    RosterEntry,
    Summary,
)
from apps.lectures.times import local_date, time_range
from apps.people.models import StudentProfile
from apps.people.ui import StudentTable
from apps.ui.components.actions import IconButton
from apps.ui.components.data import Badge, Column, DataTable, PersonCell, StatCard
from apps.ui.components.layout import Grid

# SPEC table of statuses: green, amber, amber, red.
STATUS_TONES = {
    AttendanceStatus.PRESENT: "success",
    AttendanceStatus.PARTIAL: "warning",
    AttendanceStatus.LATE: "warning",
    AttendanceStatus.ABSENT: "danger",
}
NOT_MARKED = "Not marked"
WAITING = "Waiting for teacher"
NO_MARKS = "No marks yet"


def attendance_badge(status: str, *, waiting: bool = False) -> Badge:
    """A mark, or a grey badge when the teacher has not marked it: "Not
    marked" for staff, "Waiting for teacher" (``waiting``) for students and
    guardians (audit P4-5)."""
    if not status:
        return Badge(WAITING if waiting else NOT_MARKED, tone="neutral")
    return Badge(AttendanceStatus(status).label, tone=STATUS_TONES[status])


def present_total(count: LectureCount | None) -> str:
    """Lecture History "Present / Total": present, late or partial out of
    the expected students; "Not taken" before the first mark."""
    if count is None or not count.marked:
        return "Not taken"
    return f"{count.attended} / {count.total}"


class RosterTable(DataTable):
    """The marks of one lecture, on its page."""

    empty_title = "No students are enrolled in this batch and subject."

    def __init__(self, rows: list[RosterEntry], **props):
        super().__init__(rows=rows, **props)

    @property
    def columns(self) -> list[Column]:  # type: ignore[override]
        return [
            Column(
                "student",
                "Student",
                lambda entry: PersonCell(
                    str(entry.student), detail=entry.student.student_code
                ),
            ),
            Column(
                "status", "Attendance", lambda entry: attendance_badge(entry.status)
            ),
        ]


def percent_text(percent: Decimal | None) -> str:
    """Example: 87.5%, 100%; a dash before the first finished class."""
    if percent is None:
        return "-"
    text = f"{percent:.1f}"
    return f"{text.removesuffix('.0')}%"


def attendance_value(percent: Decimal | None) -> str:
    """A card or dashboard value: the %, or "No marks yet" (audit P4-5)."""
    return NO_MARKS if percent is None else percent_text(percent)


def classes_note(summary: Summary) -> str:
    """Example: 3 of 5 finished classes marked; 5 finished classes."""
    classes = "class" if summary.total == 1 else "classes"
    if summary.not_marked:
        return f"{summary.marked} of {summary.total} finished {classes} marked"
    return f"{summary.total} finished {classes}"


def waiting_line(summary: Summary) -> str:
    """Why the % leaves some classes out; empty when none is waiting."""
    count = summary.not_marked
    if not count:
        return ""
    if count == 1:
        return (
            "1 class is waiting for the teacher to mark attendance. "
            "It is not counted yet."
        )
    return (
        f"{count} classes are waiting for the teacher to mark attendance. "
        "They are not counted yet."
    )


def summary_cards(summary: Summary) -> Grid:
    """Attendance %, Present, Partial and Absent for a student (SPEC 6.3).
    The % counts marked classes only (owner decision 2026-10-14)."""
    return Grid(
        [
            StatCard(
                attendance_value(summary.percent),
                "Attendance",
                note=classes_note(summary),
                icon="clipboard-check",
                tone="lead",
            ),
            StatCard(
                summary.present, "Present", note=f"{summary.late} late", icon="check"
            ),
            StatCard(summary.partial, "Partial", note="Counts as half", icon="clock"),
            StatCard(summary.absent, "Absent", icon="x"),
        ],
        variant="stats",
    )


def _subjects(record: Record) -> str:
    return ", ".join(sorted(subject.name for subject in record.lecture.subjects.all()))


class AttendanceTable(DataTable):
    """A student's finished lectures with their marks (My attendance, Class
    attendance, Student attendance history)."""

    empty_title = "No finished classes match these filters."

    def __init__(self, rows: list[Record], *, waiting: bool = False, **props):
        self.waiting = waiting
        super().__init__(rows=rows, **props)

    @property
    def columns(self) -> list[Column]:  # type: ignore[override]
        return [
            Column("date", "Date", lambda record: local_date(record.lecture.starts_at)),
            Column(
                "time",
                "Time",
                lambda record: time_range(
                    record.lecture.starts_at, record.lecture.ends_at
                ),
            ),
            Column("title", "Lecture", lambda record: record.lecture.title),
            Column("subjects", "Subjects", _subjects),
            Column("teacher", "Teacher", lambda record: str(record.lecture.teacher)),
            Column(
                "status",
                "Attendance",
                lambda record: attendance_badge(record.status, waiting=self.waiting),
            ),
        ]


class SummaryTable(DataTable):
    """Counts and % per month or per subject (roadmap 4.3). ``label`` names
    the first column."""

    def __init__(self, rows: list[GroupSummary], *, label: str, **props):
        self.label = label
        super().__init__(rows=rows, **props)

    @property
    def columns(self) -> list[Column]:  # type: ignore[override]
        return [
            Column("label", self.label, lambda row: row.label),
            Column("classes", "Classes", lambda row: row.summary.total),
            Column("present", "Present", lambda row: row.summary.present),
            Column("late", "Late", lambda row: row.summary.late),
            Column("partial", "Partial", lambda row: row.summary.partial),
            Column("absent", "Absent", lambda row: row.summary.absent),
            Column("not_marked", NOT_MARKED, lambda row: row.summary.not_marked),
            Column(
                "percent", "Attendance", lambda row: percent_text(row.summary.percent)
            ),
        ]


def _history_button(student: StudentProfile) -> IconButton:
    """The same link as the row action on All students."""
    history = reverse("admin:student_attendance_history")
    return IconButton(
        "clipboard-list",
        f"Attendance history of {student}",
        url=f"{history}?{urlencode({'student': student.pk})}",
    )


class StudentPickTable(StudentTable):
    """Search results on Student attendance history (audit P4-2): the
    All students columns that tell students apart, and one link each."""

    columns = [
        *(
            c
            for c in StudentTable.columns
            if c.key in {"name", "class_label", "batches"}
        ),
        Column("actions", "", _history_button),
    ]
