"""Attendance badges and tables (roadmap 4.1 to 4.3, SPEC 6.3)."""

from __future__ import annotations

from apps.attendance.models import AttendanceStatus
from apps.attendance.services import LectureCount, RosterEntry
from apps.ui.components.data import Badge, Column, DataTable, PersonCell

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
