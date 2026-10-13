"""Lecture and schedule tables (SPEC section 3: All Lectures, My Lectures,
Recurring Schedules) and the schedule preview (SPEC 4.6)."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from django.urls import reverse
from django.utils.dateformat import format as date_format

from apps.lectures.models import (
    DeliveryMode,
    Lecture,
    LectureStatus,
    RecurringSchedule,
    ScheduleStatus,
)
from apps.lectures.times import local_date, time_range
from apps.ui.components.actions import ConfirmDialog, IconButton
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


def schedule_time(schedule: RecurringSchedule) -> str:
    """The start time in the schedule's own zone, for example 10:00 AM PKT."""
    zone = ZoneInfo(schedule.time_zone)
    start = datetime.combine(schedule.start_date, schedule.start_time, tzinfo=zone)
    return date_format(start, "g:i A T")


def schedule_status_badge(schedule: RecurringSchedule) -> Badge:
    tone = "success" if schedule.status == ScheduleStatus.ACTIVE else "neutral"
    return Badge(schedule.get_status_display(), tone=tone)


def stop_dialog(schedule: RecurringSchedule, portal: str) -> ConfirmDialog:
    url = reverse(f"{portal}:lecture_schedule_stop", kwargs={"pk": schedule.pk})
    return ConfirmDialog(
        f"Stop {schedule.title}? No more lectures are made, and its lectures "
        "that have not started are cancelled.",
        "Stop",
        url=url,
    )


class ScheduleTable(DataTable):
    """Admin "Recurring schedules"; the teacher table drops the teacher."""

    portal = "admin"
    empty_title = "No schedules match these filters."

    def __init__(self, rows: list[RecurringSchedule], **props):
        super().__init__(rows=rows, **props)

    @property
    def columns(self) -> list[Column]:  # type: ignore[override]
        return [
            Column("title", "Schedule"),
            Column("teacher", "Teacher", lecture_teacher),
            Column("batch", "Batch", lambda row: row.batch.name),
            Column("days", "Days", lambda row: row.weekday_labels()),
            Column("time", "Time", schedule_time),
            Column("start", "Start", lambda row: date_format(row.start_date, "j M Y")),
            Column("end", "End", lambda row: date_format(row.end_date, "j M Y")),
            Column("lectures", "Lectures", lambda row: row.lecture_count),
            Column("status", "Status", schedule_status_badge),
            Column("actions", "", self.row_actions_for),
        ]

    def url(self, action: str, schedule: RecurringSchedule) -> str:
        name = f"{self.portal}:lecture_schedule_{action}"
        return reverse(name, kwargs={"pk": schedule.pk})

    def row_actions_for(self, schedule: RecurringSchedule) -> ButtonRow:
        if schedule.status != ScheduleStatus.ACTIVE:
            return ButtonRow(items=[])
        return ButtonRow(
            items=[
                IconButton(
                    "square-pen",
                    f"Edit {schedule.title}",
                    url=self.url("edit", schedule),
                ),
                IconButton(
                    "calendar-plus",
                    f"Extend {schedule.title}",
                    url=self.url("extend", schedule),
                ),
                stop_dialog(schedule, self.portal),
            ]
        )


class TeacherScheduleTable(ScheduleTable):
    portal = "teacher"

    @property
    def columns(self) -> list[Column]:  # type: ignore[override]
        return [column for column in super().columns if column.key != "teacher"]


class SchedulePreviewList(DataTable):
    """The lectures a schedule save would make (SPEC 4.6 preview)."""

    columns = [
        Column("date", "Date", lambda item: local_date(item.starts_at)),
        Column("time", "Time", lambda item: time_range(item.starts_at, item.ends_at)),
        Column("result", "Result", lambda item: _preview_result(item)),
    ]
    empty_title = "No lecture falls in the next weeks."


def _preview_result(item) -> Badge:
    if item.clash is None:
        return Badge("Will be added", tone="success")
    return Badge(f"Skipped: the teacher has {item.clash.title}", tone="warning")
