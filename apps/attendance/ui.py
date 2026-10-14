"""Attendance badges and tables (roadmap 4.1 to 4.3, SPEC 6.3)."""

from __future__ import annotations

from decimal import Decimal

from apps.attendance.models import AttendanceStatus
from apps.attendance.services import (
    GroupSummary,
    LectureCount,
    Record,
    RosterEntry,
    Summary,
)
from apps.lectures.times import local_date, time_range
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


def attendance_badge(status: str) -> Badge:
    """A mark, or a grey "Not marked" when the teacher has not marked it."""
    if not status:
        return Badge(NOT_MARKED, tone="neutral")
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


def summary_cards(summary: Summary) -> Grid:
    """Attendance %, Present, Partial and Absent for a student (SPEC 6.3)."""
    absent_note = f"{summary.not_marked} not marked" if summary.not_marked else ""
    classes = "class" if summary.total == 1 else "classes"
    return Grid(
        [
            StatCard(
                percent_text(summary.percent),
                "Attendance",
                note=f"{summary.total} finished {classes}",
                icon="clipboard-check",
                tone="lead",
            ),
            StatCard(
                summary.present, "Present", note=f"{summary.late} late", icon="check"
            ),
            StatCard(summary.partial, "Partial", note="Counts as half", icon="clock"),
            StatCard(
                summary.absent + summary.not_marked,
                "Absent",
                note=absent_note,
                icon="x",
            ),
        ],
        variant="stats",
    )


def _subjects(record: Record) -> str:
    return ", ".join(sorted(subject.name for subject in record.lecture.subjects.all()))


class AttendanceTable(DataTable):
    """A student's finished lectures with their marks (My attendance, Class
    attendance, Student attendance history)."""

    empty_title = "No finished classes match these filters."

    def __init__(self, rows: list[Record], **props):
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
                "status", "Attendance", lambda record: attendance_badge(record.status)
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
