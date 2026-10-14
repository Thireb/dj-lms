"""Lecture and schedule tables (SPEC section 3: All Lectures, My Lectures,
Recurring Schedules), the schedule preview (SPEC 4.6) and the teacher's
calendar days (roadmap 3.3)."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from django.urls import reverse
from django.utils import timezone
from django.utils.dateformat import format as date_format

from apps.lectures.models import (
    DeliveryMode,
    Lecture,
    LectureStatus,
    RecurringSchedule,
    ScheduleStatus,
)
from apps.lectures.services import (
    DEFAULT_JOIN_WINDOW,
    JOIN_ENDED,
    JOIN_NONE,
    JOIN_OPEN,
    JOIN_SOON,
    JOIN_WAITING,
    OPEN_STATUSES,
    can_start,
    join_opens_at,
    join_state,
    taught_minutes,
)
from apps.lectures.times import local_date, local_time, time_range
from apps.ui.components.actions import Button, ConfirmDialog, IconButton, PostButton
from apps.ui.components.block_stack import ButtonRow
from apps.ui.components.data import Badge, Column, DataTable, PersonCell
from apps.ui.components.lectures import CalendarDay, CalendarItem, CountdownCard

STATUS_TONES = {
    LectureStatus.SCHEDULED: "info",
    LectureStatus.LIVE: "success",
    LectureStatus.FINISHED: "neutral",
    LectureStatus.NOT_HELD: "warning",
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


def lecture_url(portal: str, action: str, lecture: Lecture) -> str:
    return reverse(f"{portal}:lecture_{action}", kwargs={"pk": lecture.pk})


def can_cancel(lecture: Lecture, now: datetime) -> bool:
    return lecture.status == LectureStatus.SCHEDULED and now < lecture.ends_at


def cancel_dialog(lecture: Lecture, portal: str = "admin") -> ConfirmDialog:
    return ConfirmDialog(
        f"Cancel {lecture.title}? Students see it as cancelled, and a schedule "
        "edit does not bring it back.",
        "Cancel lecture",
        url=lecture_url(portal, "cancel", lecture),
        trigger_label="Cancel",
        dismiss_label="Keep lecture",
    )


def start_button(lecture: Lecture) -> PostButton:
    return PostButton(
        "Start class", lecture_url("teacher", "start", lecture), icon="video"
    )


def end_dialog(lecture: Lecture) -> ConfirmDialog:
    return ConfirmDialog(
        f"End {lecture.title} now? Students can no longer join.",
        "End class",
        url=lecture_url("teacher", "end", lecture),
        variant="primary",
    )


class LectureTable(DataTable):
    """Admin "All lectures"; the teacher table drops the teacher column and
    has Start instead of Cancel."""

    portal = "admin"
    empty_title = "No lectures match these filters."

    def __init__(
        self,
        rows: list[Lecture],
        *,
        window: int = DEFAULT_JOIN_WINDOW,
        now: datetime | None = None,
        **props,
    ):
        self.window = window
        self.now = now or timezone.now()
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
        title = lecture.title
        items: list[Any] = [
            IconButton(
                "eye", f"View {title}", url=lecture_url(self.portal, "detail", lecture)
            )
        ]
        if has_open_link(lecture):
            items.append(
                IconButton(
                    "video",
                    f"Open meeting link for {title}",
                    url=lecture.meeting_url,
                    new_tab=True,
                )
            )
        if lecture.status == LectureStatus.SCHEDULED:
            url = lecture_url(self.portal, "edit", lecture)
            items.append(IconButton("square-pen", f"Edit {title}", url=url))
        items.extend(self.state_actions(lecture))
        return ButtonRow(items=items)

    def state_actions(self, lecture: Lecture) -> list[Any]:
        return [cancel_dialog(lecture)] if can_cancel(lecture, self.now) else []


class TeacherLectureTable(LectureTable):
    portal = "teacher"

    @property
    def columns(self) -> list[Column]:  # type: ignore[override]
        return [column for column in super().columns if column.key != "teacher"]

    def state_actions(self, lecture: Lecture) -> list[Any]:
        if can_start(lecture, now=self.now, window=self.window):
            return [start_button(lecture)]
        return []


def history_duration(lecture: Lecture) -> str:
    return f"{taught_minutes(lecture)} min"


class HistoryTable(DataTable):
    """Teacher "Lecture history" (SPEC 3); the admin table adds the teacher.
    Present / Total comes with attendance (Phase 4)."""

    portal = "teacher"
    empty_title = "No finished lectures yet."
    show_teacher = False

    def __init__(self, rows: list[Lecture], **props):
        super().__init__(rows=rows, **props)

    @property
    def columns(self) -> list[Column]:  # type: ignore[override]
        columns = [
            Column("date", "Date", lecture_date),
            Column("title", "Lecture"),
            Column("batch", "Batch", lambda lecture: lecture.batch.name),
            Column("subjects", "Subjects", lecture_subjects),
            Column("duration", "Duration", history_duration),
            Column("attendance", "Present / Total", lambda lecture: "Not taken"),
            Column("actions", "", self.view_button),
        ]
        if self.show_teacher:
            columns.insert(2, Column("teacher", "Teacher", lecture_teacher))
        return columns

    def view_button(self, lecture: Lecture) -> IconButton:
        url = lecture_url(self.portal, "detail", lecture)
        return IconButton("eye", f"View {lecture.title}", url=url)


class AdminHistoryTable(HistoryTable):
    portal = "admin"
    show_teacher = True


def lecture_detail_rows(lecture: Lecture, *, show_teacher: bool) -> list[tuple]:
    """Label and value pairs for the lecture page."""
    rows: list[tuple[str, Any]] = [
        ("Status", lecture_status_badge(lecture)),
        ("Date", lecture_date(lecture)),
        ("Time", lecture_time(lecture)),
    ]
    if show_teacher:
        rows.append(("Teacher", lecture_teacher(lecture)))
    rows += [
        ("Batch", lecture.batch.name),
        ("Subjects", lecture_subjects(lecture)),
        ("Delivery", lecture.get_delivery_mode_display()),
    ]
    if lecture.started_at:
        rows.append(("Started", local_time(lecture.started_at)))
    if lecture.ended_at:
        rows.append(("Ended", local_time(lecture.ended_at)))
    if lecture.status == LectureStatus.FINISHED:
        rows.append(("Taught", history_duration(lecture)))
    if lecture.schedule_id:
        rows.append(("Schedule", lecture.schedule.title))
    rows.append(("Description", lecture.description))
    return rows


class StudentLectureTable(LectureTable):
    """Student "My lectures" (with Join) and the guardian's lectures for one
    child (``join_window=None``: guardians do not join)."""

    portal = "student"

    def __init__(
        self,
        rows: list[Lecture],
        *,
        join_window: int | None = None,
        now: datetime | None = None,
        **props,
    ):
        self.join_window = join_window
        self.now = now or timezone.now()
        super().__init__(rows, **props)

    @property
    def columns(self) -> list[Column]:  # type: ignore[override]
        columns = [
            Column("title", "Lecture"),
            Column("date", "Date", lecture_date),
            Column("time", "Time", lecture_time),
            Column("subjects", "Subjects", lecture_subjects),
            Column("teacher", "Teacher", lambda lecture: str(lecture.teacher)),
            Column("status", "Status", lecture_status_badge),
        ]
        if self.join_window is not None:
            columns.append(Column("join", "Join", self.join_for))
        return columns

    def join_for(self, lecture: Lecture) -> Any:
        window = self.join_window or 0
        state = join_state(lecture, now=self.now, window=window)
        return join_action(lecture, state, window)


JOIN_LABELS = {
    JOIN_SOON: "Join opens soon",
    JOIN_WAITING: "Waiting for host",
    JOIN_ENDED: "Ended",
}


def join_action(lecture: Lecture, state: str, window: int) -> Any:
    """The student's Join button for a state (SPEC 6.4). Only the open state
    is a real button; it posts to the join view, which opens the link."""
    if state == JOIN_OPEN:
        url = reverse("student:lecture_join", kwargs={"pk": lecture.pk})
        return PostButton("Join", url, icon="video", new_tab=True)
    if state == JOIN_NONE:
        in_person = lecture.delivery_mode == DeliveryMode.IN_PERSON
        return (
            "In person"
            if in_person and lecture.status != LectureStatus.CANCELLED
            else ""
        )
    title = ""
    if state == JOIN_SOON:
        title = f"Join opens at {local_time(join_opens_at(lecture, window))}."
    return Button(JOIN_LABELS[state], variant="secondary", disabled=True, title=title)


def lecture_when(lecture: Lecture) -> str:
    """Example: Wed 14 Oct 2026, 3:00 PM to 4:00 PM PKT."""
    return f"{lecture_date(lecture)}, {lecture_time(lecture)}"


def lecture_summary(lecture: Lecture, *, teacher: bool = False) -> str:
    parts = [lecture.batch.name, lecture_subjects(lecture)]
    if teacher:
        parts.append(str(lecture.teacher))
    return " · ".join(part for part in parts if part)


def up_next_card(
    lecture: Lecture, *, action: Any, refresh_url: str, teacher: bool = False
) -> CountdownCard:
    return CountdownCard(
        lecture.title,
        lecture.starts_at,
        when=lecture_when(lecture),
        detail=lecture_summary(lecture, teacher=teacher),
        action=action,
        refresh_url=refresh_url,
    )


def has_open_link(lecture: Lecture) -> bool:
    """A meeting link worth showing: online, and not finished or cancelled."""
    return (
        lecture.delivery_mode == DeliveryMode.MANUAL_LINK
        and bool(lecture.meeting_url)
        and lecture.status in OPEN_STATUSES
    )


def meeting_link_button(lecture: Lecture) -> Button | None:
    """The teacher's and admin's way into the meeting."""
    if not has_open_link(lecture):
        return None
    return Button("Open meeting link", url=lecture.meeting_url, icon="video")


def calendar_item(lecture: Lecture, url: str | None) -> CalendarItem:
    return CalendarItem(
        time=lecture_time(lecture),
        title=lecture.title,
        detail=f"{lecture.batch.name} · {lecture_subjects(lecture)}",
        status=lecture.get_status_display(),
        tone=STATUS_TONES[lecture.status],
        url=url,
    )


def calendar_days(
    lectures: Iterable[Lecture],
    days: list[date],
    *,
    today: date,
    month: date | None,
    url_for: Callable[[Lecture], str | None],
) -> list[CalendarDay]:
    """One ``CalendarDay`` per day, with its lectures by the viewer's date."""
    items: dict[date, list[CalendarItem]] = defaultdict(list)
    for lecture in lectures:
        day = timezone.localtime(lecture.starts_at).date()
        items[day].append(calendar_item(lecture, url_for(lecture)))
    return [
        CalendarDay(
            day=day,
            items=items.get(day, []),
            is_today=day == today,
            in_month=month is None or day.month == month.month,
        )
        for day in days
    ]


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
        Column("note", "Note", lambda item: _preview_note(item)),
    ]
    empty_title = "No lecture falls in the next weeks."


def _preview_result(item) -> Badge:
    if item.clash is None:
        return Badge("Will be added", tone="success")
    return Badge("Skipped", tone="warning")


def _preview_note(item) -> str:
    # Plain text wraps on phones; a badge with the title did not fit at 360px.
    if item.clash is None:
        return ""
    return f"The teacher already has {item.clash.title} then."


# Live lecture monitor (roadmap 3.6)


def minutes_text(delta: timedelta) -> str:
    """Example: 25 min, 1 h 05 min; under a minute is "Just now"."""
    minutes = int(delta.total_seconds() // 60)
    if minutes < 1:
        return "Just now"
    if minutes < 60:
        return f"{minutes} min"
    return f"{minutes // 60} h {minutes % 60:02d} min"


class MonitorTable(DataTable):
    """One list of the Lectures dashboard. ``mode``: ``live`` (started at,
    running for), ``late`` (planned start, late by) or ``soon`` (time,
    starts in)."""

    MODES = {
        "live": ("No lecture is live now.", "Started", "Running for"),
        "late": ("No lecture is late.", "Planned start", "Late by"),
        "soon": ("Nothing starts in the next 2 hours.", "Time", "Starts in"),
    }

    def __init__(self, rows: list[Lecture], *, mode: str, now: datetime, **props):
        self.mode = mode
        self.now = now
        super().__init__(rows=rows, empty_title=self.MODES[mode][0], **props)

    @property
    def columns(self) -> list[Column]:  # type: ignore[override]
        _, when_label, wait_label = self.MODES[self.mode]
        return [
            Column("title", "Lecture"),
            Column("teacher", "Teacher", lecture_teacher),
            Column("batch", "Batch and subjects", lecture_summary),
            Column("when", when_label, self.when),
            Column("wait", wait_label, self.wait),
            Column("actions", "", self.actions),
        ]

    def when(self, lecture: Lecture) -> str:
        if self.mode == "live" and lecture.started_at:
            return local_time(lecture.started_at)
        if self.mode == "soon":
            return lecture_time(lecture)
        return local_time(lecture.starts_at)

    def wait(self, lecture: Lecture) -> str:
        if self.mode == "live":
            return minutes_text(self.now - (lecture.started_at or lecture.starts_at))
        if self.mode == "late":
            return minutes_text(self.now - lecture.starts_at)
        return minutes_text(lecture.starts_at - self.now)

    def actions(self, lecture: Lecture) -> ButtonRow:
        items: list[Any] = [
            IconButton(
                "eye",
                f"View {lecture.title}",
                url=lecture_url("admin", "detail", lecture),
            )
        ]
        if has_open_link(lecture):
            items.append(
                IconButton(
                    "video",
                    f"Open meeting link for {lecture.title}",
                    url=lecture.meeting_url,
                    new_tab=True,
                )
            )
        return ButtonRow(items=items)
