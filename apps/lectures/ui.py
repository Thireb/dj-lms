"""Lecture tables and badges (SPEC section 3: All Lectures, My Lectures)."""

from __future__ import annotations

from django.urls import reverse

from apps.lectures.models import DeliveryMode, Lecture, LectureStatus
from apps.lectures.times import local_date, time_range
from apps.ui.components.actions import IconButton
from apps.ui.components.block_stack import ButtonRow
from apps.ui.components.data import Badge, Column, DataTable, PersonCell

STATUS_TONES = {
    LectureStatus.SCHEDULED: "info",
    LectureStatus.LIVE: "success",
    LectureStatus.FINISHED: "neutral",
    LectureStatus.CANCELLED: "danger",
}


def lecture_status_badge(lecture: Lecture) -> Badge:
    return Badge(lecture.get_status_display(), tone=STATUS_TONES[lecture.status])


def lecture_date(lecture: Lecture) -> str:
    return local_date(lecture.starts_at)


def lecture_time(lecture: Lecture) -> str:
    return time_range(lecture.starts_at, lecture.ends_at)


def lecture_subjects(lecture: Lecture) -> str:
    return ", ".join(sorted(subject.name for subject in lecture.subjects.all()))


def lecture_teacher(lecture: Lecture) -> PersonCell:
    return PersonCell(str(lecture.teacher), detail=lecture.teacher.teacher_code)


class LectureTable(DataTable):
    """Admin "All lectures"; the teacher table drops the teacher column."""

    portal = "admin"
    empty_title = "No lectures match these filters."

    def __init__(self, rows: list[Lecture], **props):
        super().__init__(rows=rows, **props)

    @property
    def columns(self) -> list[Column]:  # type: ignore[override]
        return [
            Column("title", "Lecture"),
            Column("date", "Date", lecture_date),
            Column("time", "Time", lecture_time),
            Column("teacher", "Teacher", lecture_teacher),
            Column("batch", "Batch", lambda lecture: lecture.batch.name),
            Column("subjects", "Subjects", lecture_subjects),
            Column("mode", "Mode", lambda lecture: lecture.get_delivery_mode_display()),
            Column("status", "Status", lecture_status_badge),
            Column("actions", "", self.row_actions_for),
        ]

    def row_actions_for(self, lecture: Lecture) -> ButtonRow:
        items = []
        if lecture.delivery_mode == DeliveryMode.MANUAL_LINK and lecture.meeting_url:
            items.append(
                IconButton(
                    "video",
                    f"Open meeting link for {lecture.title}",
                    url=lecture.meeting_url,
                    new_tab=True,
                )
            )
        if lecture.status == LectureStatus.SCHEDULED:
            url = reverse(f"{self.portal}:lecture_edit", kwargs={"pk": lecture.pk})
            items.append(IconButton("square-pen", f"Edit {lecture.title}", url=url))
        return ButtonRow(items=items)


class TeacherLectureTable(LectureTable):
    portal = "teacher"

    @property
    def columns(self) -> list[Column]:  # type: ignore[override]
        return [column for column in super().columns if column.key != "teacher"]
