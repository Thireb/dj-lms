"""Create, edit and list lectures (roadmap 3.1, SPEC 4.5 and 6.4), and the
recurring schedules that make them (roadmap 3.2, SPEC 4.6)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import (
    Count,
    DateTimeField,
    DurationField,
    ExpressionWrapper,
    F,
    QuerySet,
)
from django.utils import timezone

from apps.academics.models import Batch, Subject, TeacherBatchSubject
from apps.core.tenancy import require_tenant_context
from apps.institutes.models import Institute, InstituteSettings
from apps.lectures.models import (
    MAX_DURATION,
    MIN_DURATION,
    DeliveryMode,
    Lecture,
    LectureQuerySet,
    LectureStatus,
    RecurringSchedule,
    ScheduleStatus,
    Weekday,
    meeting_url_validator,
)
from apps.lectures.providers import provider_for
from apps.lectures.times import (
    combine_local,
    local_date,
    local_day_bounds,
    local_time,
    time_range,
)
from apps.people.models import ProfileStatus, TeacherProfile

SHOW_UPCOMING = "upcoming"
SHOW_CHOICES = [
    ("today", "Today"),
    (SHOW_UPCOMING, "Upcoming"),
    ("past", "Past"),
    ("all", "All"),
]

ENDS_AT = ExpressionWrapper(
    F("starts_at")
    + ExpressionWrapper(
        F("duration_minutes") * timedelta(minutes=1), output_field=DurationField()
    ),
    output_field=DateTimeField(),
)


@dataclass(frozen=True)
class LectureDetails:
    title: str
    teacher: TeacherProfile
    batch: Batch
    subjects: list[Subject]
    starts_at: datetime
    duration_minutes: int
    delivery_mode: str
    meeting_url: str = ""
    description: str = ""


@dataclass(frozen=True)
class SavedLecture:
    lecture: Lecture
    # Other lectures of the same batch at the same time: a warning only.
    batch_clashes: list[Lecture] = field(default_factory=list)


class _Errors:
    def __init__(self) -> None:
        self.by_field: dict[str, list[str]] = {}

    def add(self, name: str, message: str) -> None:
        self.by_field.setdefault(name, []).append(message)

    def raise_any(self) -> None:
        if self.by_field:
            raise ValidationError(self.by_field)


def _overlapping(lectures: Any, starts_at: datetime, ends_at: datetime) -> Any:
    """Lectures (not cancelled) that share any minute with the time slot."""
    return (
        lectures.exclude(status=LectureStatus.CANCELLED)
        .annotate(ends_at_db=ENDS_AT)
        .filter(starts_at__lt=ends_at, ends_at_db__gt=starts_at)
        .order_by("starts_at")
    )


def _describe(lecture: Lecture) -> str:
    when = time_range(lecture.starts_at, lecture.ends_at)
    return f"{lecture.title} on {local_date(lecture.starts_at)}, {when}"


def _check_people(
    errors: _Errors, institute: Institute, details: LectureDetails, old: Lecture | None
) -> None:
    teacher, batch = details.teacher, details.batch
    for name, row in (("teacher", teacher), ("batch", batch)):
        if row.institute_id != institute.pk:
            errors.add(name, "Must belong to the same institute.")
            return
    if any(subject.institute_id != institute.pk for subject in details.subjects):
        errors.add("subjects", "Must belong to the same institute.")
        return
    if not details.subjects:
        errors.add("subjects", "Choose at least one subject.")
        return
    old_teacher = old.teacher_id if old else None
    if teacher.status != ProfileStatus.ACTIVE and teacher.pk != old_teacher:
        errors.add("teacher", "This teacher is inactive.")
    old_batch = old.batch_id if old else None
    if not batch.is_active and batch.pk != old_batch:
        errors.add("batch", f"{batch.name} is inactive.")
    old_subjects = {s.pk for s in old.subjects.all()} if old else set()
    for subject in details.subjects:
        if not subject.is_active and subject.pk not in old_subjects:
            errors.add("subjects", f"{subject.name} is inactive.")
    taught = set(
        TeacherBatchSubject.objects.filter(teacher=teacher, batch=batch).values_list(
            "subject_id", flat=True
        )
    )
    for subject in details.subjects:
        if subject.pk not in taught:
            errors.add(
                "subjects",
                f"{teacher} does not teach {subject.name} in {batch.name}.",
            )


def _check_time(errors: _Errors, details: LectureDetails, old: Lecture | None) -> None:
    if not MIN_DURATION <= details.duration_minutes <= MAX_DURATION:
        errors.add(
            "duration_minutes",
            f"Enter a duration from {MIN_DURATION} to {MAX_DURATION} minutes.",
        )
    moved = old is None or old.starts_at != details.starts_at
    if moved and details.starts_at <= timezone.now():
        errors.add("starts_at", "Choose a start time in the future.")


def _check_link(errors: _Errors, details: LectureDetails) -> None:
    if details.delivery_mode not in DeliveryMode.values:
        errors.add("delivery_mode", "Choose a delivery mode.")
        return
    link = details.meeting_url.strip()
    if details.delivery_mode != DeliveryMode.MANUAL_LINK:
        return
    if not link:
        errors.add("meeting_url", "Paste the meeting link for an online lecture.")
        return
    try:
        meeting_url_validator(link)
    except ValidationError:
        errors.add("meeting_url", "Enter a full link that starts with https://.")


def _check_teacher_free(
    errors: _Errors, details: LectureDetails, old: Lecture | None
) -> None:
    ends_at = details.starts_at + timedelta(minutes=details.duration_minutes)
    others = Lecture.objects.filter(teacher=details.teacher)
    if old is not None:
        others = others.exclude(pk=old.pk)
    clash = _overlapping(others, details.starts_at, ends_at).first()
    if clash is not None:
        errors.add("starts_at", f"{details.teacher} already has {_describe(clash)}.")


def _batch_clashes(lecture: Lecture) -> list[Lecture]:
    others = Lecture.objects.filter(batch=lecture.batch).exclude(pk=lecture.pk)
    return list(_overlapping(others, lecture.starts_at, lecture.ends_at))


def _check(institute: Institute, details: LectureDetails, old: Lecture | None) -> None:
    errors = _Errors()
    if old is not None and old.status != LectureStatus.SCHEDULED:
        errors.add("__all__", "Only a scheduled lecture can be edited.")
        errors.raise_any()
    if not details.title.strip():
        errors.add("title", "Enter a title.")
    _check_people(errors, institute, details, old)
    _check_time(errors, details, old)
    _check_link(errors, details)
    errors.raise_any()
    _check_teacher_free(errors, details, old)
    errors.raise_any()


def _lock_and_reload(row: Lecture | RecurringSchedule) -> None:
    """Lock the row and read it again, so a check and save see the latest
    state: a Start, Cancel or the finish job between the page load and the
    save is not undone by saving the old values (Phase 3 audit P3-2)."""
    type(row).objects.select_for_update().filter(pk=row.pk).first()
    row.refresh_from_db()


def _lock_teacher(teacher: TeacherProfile) -> None:
    """Two saves for one teacher run one after the other, so the overlap check
    in the second one sees the first lecture."""
    TeacherProfile.objects.select_for_update().filter(pk=teacher.pk).first()


def _apply(lecture: Lecture, details: LectureDetails) -> SavedLecture:
    lecture.title = details.title.strip()
    lecture.teacher = details.teacher
    lecture.batch = details.batch
    lecture.starts_at = details.starts_at
    lecture.duration_minutes = details.duration_minutes
    lecture.delivery_mode = details.delivery_mode
    lecture.description = details.description.strip()
    provider = provider_for(details.delivery_mode)
    lecture.meeting_url = provider.create_meeting(lecture, details.meeting_url)
    lecture.save()
    lecture.subjects.set(details.subjects)
    return SavedLecture(lecture=lecture, batch_clashes=_batch_clashes(lecture))


@transaction.atomic
def create_lecture(institute: Institute, details: LectureDetails) -> SavedLecture:
    require_tenant_context(institute)
    _lock_teacher(details.teacher)
    _check(institute, details, None)
    return _apply(Lecture(institute=institute), details)


@transaction.atomic
def update_lecture(lecture: Lecture, details: LectureDetails) -> SavedLecture:
    """Edit one lecture. A schedule's lecture edited here ("this one") keeps
    its changes when the schedule is edited later."""
    require_tenant_context(lecture.institute)
    _lock_teacher(details.teacher)
    _lock_and_reload(lecture)
    _check(lecture.institute, details, lecture)
    if lecture.schedule_id is not None:
        lecture.follows_schedule = False
    return _apply(lecture, details)


def list_lectures(
    user: Any,
    *,
    show: str = SHOW_UPCOMING,
    teacher_id: int | None = None,
    batch_id: int | None = None,
    subject_id: int | None = None,
    student_id: int | None = None,
    status: str = "",
    date_from: date | None = None,
    date_to: date | None = None,
    now: datetime | None = None,
) -> LectureQuerySet:
    """Lectures the user may see, for the Today, Upcoming, Past or All view.

    ``student_id`` keeps the lectures of one student (a guardian's chosen
    child); the caller checks that the user may see that student.
    ``date_from`` and ``date_to`` are days in the viewer's time zone, both
    included."""
    now = now or timezone.now()
    lectures = (
        Lecture.objects.for_user(user)
        .select_related("teacher__user", "batch")
        .prefetch_related("subjects")
        .annotate(ends_at_db=ENDS_AT)
    )
    if teacher_id is not None:
        lectures = lectures.filter(teacher_id=teacher_id)
    if batch_id is not None:
        lectures = lectures.filter(batch_id=batch_id)
    if subject_id is not None:
        lectures = lectures.filter(subjects__id=subject_id).distinct()
    if student_id is not None:
        # One filter() call: the same enrolment row has the student and batch.
        lectures = lectures.filter(
            subjects__student_links__student_id=student_id,
            subjects__student_links__batch_id=F("batch_id"),
        ).distinct()
    if status in LectureStatus.values:
        lectures = lectures.filter(status=status)
    if date_from is not None:
        lectures = lectures.filter(starts_at__gte=combine_local(date_from, time.min))
    if date_to is not None:
        day_after = date_to + timedelta(days=1)
        lectures = lectures.filter(starts_at__lt=combine_local(day_after, time.min))
    if show == "today":
        start, end = local_day_bounds(now)
        lectures = lectures.filter(starts_at__gte=start, starts_at__lt=end)
    elif show == "past":
        return lectures.filter(ends_at_db__lte=now).order_by("-starts_at", "-pk")
    elif show == SHOW_UPCOMING:
        lectures = lectures.filter(ends_at_db__gt=now)
    return lectures.order_by("starts_at", "pk")


# Up next and joining (roadmap 3.4, SPEC 6.4)

DEFAULT_JOIN_WINDOW = 10
JOIN_SOON = "soon"  # before the join window opens
JOIN_WAITING = "waiting"  # window open, the teacher has not started
JOIN_OPEN = "open"  # the teacher started: students may join
JOIN_ENDED = "ended"
JOIN_NONE = "none"  # cancelled, or in person: nothing to join
OPEN_STATUSES = (LectureStatus.SCHEDULED, LectureStatus.LIVE)
CLOSED_STATUSES = (LectureStatus.FINISHED, LectureStatus.NOT_HELD)


def join_window_minutes(institute: Institute | None) -> int:
    minutes = (
        InstituteSettings.objects.filter(institute=institute)
        .values_list("join_window_minutes", flat=True)
        .first()
    )
    return DEFAULT_JOIN_WINDOW if minutes is None else minutes


def join_opens_at(lecture: Lecture, window: int) -> datetime:
    return lecture.starts_at - timedelta(minutes=window)


def join_state(lecture: Lecture, *, now: datetime, window: int) -> str:
    """The student's Join state. Join opens at start minus the window; it is
    enabled once the teacher starts (status live) and ends with the lecture."""
    if (
        lecture.status == LectureStatus.CANCELLED
        or lecture.delivery_mode != DeliveryMode.MANUAL_LINK
    ):
        return JOIN_NONE
    if lecture.status in CLOSED_STATUSES or now >= lecture.ends_at:
        return JOIN_ENDED
    if lecture.status == LectureStatus.LIVE:
        return JOIN_OPEN
    if now < join_opens_at(lecture, window):
        return JOIN_SOON
    return JOIN_WAITING


def _open_lectures(user: Any, now: datetime) -> QuerySet:
    """Scheduled or live lectures the user may see that have not ended."""
    return (
        Lecture.objects.for_user(user)
        .filter(status__in=OPEN_STATUSES)
        .annotate(ends_at_db=ENDS_AT)
        .filter(ends_at_db__gt=now)
        .select_related("teacher__user", "batch")
        .prefetch_related("subjects")
        .order_by("starts_at", "pk")
    )


def next_lecture(user: Any, *, now: datetime | None = None) -> Lecture | None:
    """The user's next lecture: the running one, or the next to start."""
    return _open_lectures(user, now or timezone.now()).first()


def upcoming_lectures(
    user: Any, *, limit: int, now: datetime | None = None
) -> list[Lecture]:
    return list(_open_lectures(user, now or timezone.now())[:limit])


def lectures_today_count(user: Any, *, now: datetime | None = None) -> int:
    """Lectures on the viewer's today, cancelled ones left out."""
    start, end = local_day_bounds(now or timezone.now())
    return (
        Lecture.objects.for_user(user)
        .filter(starts_at__gte=start, starts_at__lt=end)
        .exclude(status=LectureStatus.CANCELLED)
        .count()
    )


# Lecture states (roadmap 3.5, SPEC 6.4)


def can_start(lecture: Lecture, *, now: datetime, window: int) -> bool:
    """The teacher may start a scheduled lecture from the join window until
    its planned end."""
    return (
        lecture.status == LectureStatus.SCHEDULED
        and join_opens_at(lecture, window) <= now < lecture.ends_at
    )


def _locked(lecture: Lecture) -> Lecture:
    """The row again, locked, so two clicks cannot both change it."""
    return Lecture.objects.select_for_update().get(pk=lecture.pk)


def start_lecture(
    lecture: Lecture, *, window: int, now: datetime | None = None
) -> Lecture:
    now = now or timezone.now()
    with transaction.atomic():
        lecture = _locked(lecture)
        if not can_start(lecture, now=now, window=window):
            opens = local_time(join_opens_at(lecture, window))
            raise ValidationError(
                f"Only a scheduled lecture can be started, from {opens} "
                "until its end time."
            )
        lecture.status = LectureStatus.LIVE
        lecture.started_at = now
        lecture.save(update_fields=["status", "started_at", "updated_at"])
    return lecture


def end_lecture(lecture: Lecture, *, now: datetime | None = None) -> Lecture:
    now = now or timezone.now()
    with transaction.atomic():
        lecture = _locked(lecture)
        if lecture.status != LectureStatus.LIVE:
            raise ValidationError("Only a live lecture can be ended.")
        lecture.status = LectureStatus.FINISHED
        lecture.ended_at = now
        lecture.save(update_fields=["status", "ended_at", "updated_at"])
    return lecture


def cancel_lecture(lecture: Lecture, *, now: datetime | None = None) -> Lecture:
    """Cancel a scheduled lecture that has not ended. A schedule edit or the
    nightly job does not bring it back."""
    now = now or timezone.now()
    with transaction.atomic():
        lecture = _locked(lecture)
        if lecture.status != LectureStatus.SCHEDULED or now >= lecture.ends_at:
            raise ValidationError(
                "Only a scheduled lecture that has not ended can be cancelled."
            )
        lecture.status = LectureStatus.CANCELLED
        lecture.follows_schedule = False
        lecture.save(update_fields=["status", "follows_schedule", "updated_at"])
    return lecture


def finish_ended_lectures(institute: Institute, now: datetime | None = None) -> int:
    """Lectures past their planned end close (SPEC 6.4: "Finish sets finished
    automatically after the end time unless ended earlier"). A live lecture
    becomes finished at its planned end; a scheduled one the teacher never
    started becomes not held (Phase 3 audit P3-7), so payroll and attendance
    do not count it. Runs in the institute's tenant context; returns the
    count of both."""
    require_tenant_context(institute)
    now = now or timezone.now()
    ended = (
        Lecture.objects.filter(status__in=OPEN_STATUSES)
        .annotate(ends_at_db=ENDS_AT)
        .filter(ends_at_db__lte=now)
    )
    finished = Lecture.objects.filter(
        pk__in=ended.filter(status=LectureStatus.LIVE).values("pk")
    ).update(status=LectureStatus.FINISHED, ended_at=ENDS_AT, updated_at=now)
    not_held = Lecture.objects.filter(
        pk__in=ended.filter(status=LectureStatus.SCHEDULED).values("pk")
    ).update(status=LectureStatus.NOT_HELD, updated_at=now)
    return finished + not_held


def taught_minutes(lecture: Lecture) -> int:
    """Minutes from Start to end when both are known, else the plan."""
    if lecture.started_at and lecture.ended_at:
        seconds = (lecture.ended_at - lecture.started_at).total_seconds()
        return max(0, round(seconds / 60))
    return lecture.duration_minutes


def list_history(
    user: Any, *, teacher_id: int | None = None, batch_id: int | None = None
) -> LectureQuerySet:
    """Finished lectures the user may see, newest first (Lecture History)."""
    lectures = (
        Lecture.objects.for_user(user)
        .filter(status=LectureStatus.FINISHED)
        .select_related("teacher__user", "batch")
        .prefetch_related("subjects")
    )
    if teacher_id is not None:
        lectures = lectures.filter(teacher_id=teacher_id)
    if batch_id is not None:
        lectures = lectures.filter(batch_id=batch_id)
    return lectures.order_by("-starts_at", "-pk")


# Live lecture monitor (roadmap 3.6, SPEC 8 Lectures dashboard)

SOON_WINDOW = timedelta(hours=2)


@dataclass(frozen=True)
class LectureMonitor:
    live: list[Lecture]
    late: list[Lecture]  # past their start, not started, not ended
    soon: list[Lecture]  # start within SOON_WINDOW
    today: dict[str, int]  # today's lectures by status

    @property
    def today_total(self) -> int:
        """Today's lectures without the cancelled ones."""
        return sum(
            count
            for status, count in self.today.items()
            if status != LectureStatus.CANCELLED
        )


def lecture_monitor(user: Any, *, now: datetime | None = None) -> LectureMonitor:
    now = now or timezone.now()
    lectures = (
        Lecture.objects.for_user(user)
        .annotate(ends_at_db=ENDS_AT)
        .select_related("teacher__user", "batch")
        .prefetch_related("subjects")
        .order_by("starts_at", "pk")
    )
    scheduled = lectures.filter(status=LectureStatus.SCHEDULED)
    start, end = local_day_bounds(now)
    today = (
        Lecture.objects.for_user(user)
        .filter(starts_at__gte=start, starts_at__lt=end)
        .values("status")
        .annotate(count=Count("pk"))
        .order_by()
    )
    return LectureMonitor(
        live=list(lectures.filter(status=LectureStatus.LIVE)),
        late=list(scheduled.filter(starts_at__lte=now, ends_at_db__gt=now)),
        soon=list(
            scheduled.filter(starts_at__gt=now, starts_at__lte=now + SOON_WINDOW)
        ),
        today={row["status"]: row["count"] for row in today},
    )


# Calendar (roadmap 3.3, SPEC 3: teacher Schedule)

CALENDAR_WEEK = "week"
CALENDAR_MONTH = "month"


@dataclass(frozen=True)
class CalendarRange:
    """The days a week or month view shows. Weeks start on Monday; a month
    view shows whole weeks, so it can start and end in the next months."""

    view: str
    first: date
    last: date
    month: date | None
    previous: date
    next: date

    @property
    def days(self) -> list[date]:
        count = (self.last - self.first).days + 1
        return [self.first + timedelta(days=offset) for offset in range(count)]


def _first_of_next_month(day: date) -> date:
    return (day.replace(day=1) + timedelta(days=32)).replace(day=1)


def calendar_range(view: str, anchor: date) -> CalendarRange:
    if view == CALENDAR_MONTH:
        month = anchor.replace(day=1)
        next_month = _first_of_next_month(month)
        month_end = next_month - timedelta(days=1)
        return CalendarRange(
            view=CALENDAR_MONTH,
            first=month - timedelta(days=month.weekday()),
            last=month_end + timedelta(days=6 - month_end.weekday()),
            month=month,
            previous=(month - timedelta(days=1)).replace(day=1),
            next=next_month,
        )
    monday = anchor - timedelta(days=anchor.weekday())
    return CalendarRange(
        view=CALENDAR_WEEK,
        first=monday,
        last=monday + timedelta(days=6),
        month=None,
        previous=monday - timedelta(days=7),
        next=monday + timedelta(days=7),
    )


def calendar_lectures(user: Any, first: date, last: date) -> list[Lecture]:
    """Lectures the user may see that start on the days first to last, in the
    viewer's time zone."""
    start = combine_local(first, time.min)
    end = combine_local(last + timedelta(days=1), time.min)
    return list(
        Lecture.objects.for_user(user)
        .filter(starts_at__gte=start, starts_at__lt=end)
        .select_related("batch")
        .prefetch_related("subjects")
        .order_by("starts_at", "pk")
    )


# Recurring schedules (roadmap 3.2, SPEC 4.6 and 6.4)

MAX_SCHEDULE_DAYS = 366
DEFAULT_HORIZON_WEEKS = 8


@dataclass(frozen=True)
class ScheduleDetails:
    title: str
    teacher: TeacherProfile
    batch: Batch
    subjects: list[Subject]
    weekdays: list[int]
    start_time: time
    duration_minutes: int
    start_date: date
    end_date: date
    time_zone: str
    delivery_mode: str
    meeting_url: str = ""
    description: str = ""


@dataclass(frozen=True)
class PlannedLecture:
    starts_at: datetime
    ends_at: datetime
    # The teacher already has this lecture then, so the date is skipped.
    clash: Lecture | None = None


@dataclass(frozen=True)
class SchedulePreview:
    planned: list[PlannedLecture]
    # Dates after the horizon; the nightly job adds them as they come near.
    later_count: int
    horizon_weeks: int

    @property
    def created_count(self) -> int:
        return sum(1 for item in self.planned if item.clash is None)


def horizon_weeks(institute: Institute) -> int:
    weeks = (
        InstituteSettings.objects.filter(institute=institute)
        .values_list("recurring_lecture_horizon_weeks", flat=True)
        .first()
    )
    return max(1, weeks or DEFAULT_HORIZON_WEEKS)


def schedule_today(time_zone: str, now: datetime) -> date:
    return timezone.localtime(now, ZoneInfo(time_zone)).date()


def occurrences(source: Any, first: date, last: date) -> list[datetime]:
    """Start times on the chosen weekdays from ``first`` to ``last``, at the
    wall-clock start time in the schedule's zone (UTC values differ when the
    zone changes its clocks)."""
    zone = ZoneInfo(source.time_zone)
    days = set(source.weekdays)
    result = []
    day = first
    while day <= last:
        if day.weekday() in days:
            result.append(datetime.combine(day, source.start_time, tzinfo=zone))
        day += timedelta(days=1)
    return result


def _window(
    institute: Institute, source: Any, now: datetime, after: date | None = None
) -> tuple[date, date]:
    today = schedule_today(source.time_zone, now)
    first = max(source.start_date, today)
    if after is not None:
        first = max(first, after + timedelta(days=1))
    last = min(source.end_date, today + timedelta(weeks=horizon_weeks(institute)))
    return first, last


def _busy(teacher: TeacherProfile, first: datetime, last: datetime, skip: Any) -> list:
    lectures = Lecture.objects.filter(
        teacher=teacher, starts_at__lt=last + timedelta(days=1)
    ).exclude(status=LectureStatus.CANCELLED)
    if skip is not None:
        lectures = lectures.exclude(pk__in=skip)
    lectures = lectures.annotate(ends_at_db=ENDS_AT).filter(ends_at_db__gt=first)
    return list(lectures)


def _plan(
    source: Any, starts: list[datetime], now: datetime, skip: Any = None
) -> list[PlannedLecture]:
    starts = [start for start in starts if start > now]
    if not starts:
        return []
    length = timedelta(minutes=source.duration_minutes)
    busy = _busy(source.teacher, starts[0], starts[-1] + length, skip)
    planned = []
    for start in starts:
        end = start + length
        clash = next(
            (lec for lec in busy if lec.starts_at < end and lec.ends_at > start), None
        )
        planned.append(PlannedLecture(starts_at=start, ends_at=end, clash=clash))
    return planned


def _future_lectures(schedule: RecurringSchedule, now: datetime) -> Any:
    """Lectures of the schedule that have not started and still follow it."""
    return Lecture.objects.filter(
        schedule=schedule,
        follows_schedule=True,
        status=LectureStatus.SCHEDULED,
        starts_at__gt=now,
    )


def _check_schedule(
    institute: Institute,
    details: ScheduleDetails,
    old: RecurringSchedule | None,
    now: datetime,
) -> None:
    errors = _Errors()
    if old is not None and old.status != ScheduleStatus.ACTIVE:
        errors.add("__all__", "A stopped schedule cannot be edited.")
        errors.raise_any()
    if not details.title.strip():
        errors.add("title", "Enter a title.")
    _check_people(errors, institute, details, old)
    if not MIN_DURATION <= details.duration_minutes <= MAX_DURATION:
        errors.add(
            "duration_minutes",
            f"Enter a duration from {MIN_DURATION} to {MAX_DURATION} minutes.",
        )
    _check_link(errors, details)
    _check_dates(errors, details, old, now)
    errors.raise_any()


def _check_dates(
    errors: _Errors,
    details: ScheduleDetails,
    old: RecurringSchedule | None,
    now: datetime,
) -> None:
    if not details.weekdays or not set(details.weekdays) <= set(Weekday.values):
        errors.add("weekdays", "Choose at least one day.")
        return
    try:
        ZoneInfo(details.time_zone)
    except (ValueError, KeyError):
        errors.add("__all__", "Unknown time zone.")
        return
    moved = old is None or old.start_date != details.start_date
    if moved and details.start_date < schedule_today(details.time_zone, now):
        errors.add("start_date", "Choose a start date from today on.")
    if details.end_date < details.start_date:
        errors.add("end_date", "The end date is before the start date.")
        return
    if (details.end_date - details.start_date).days >= MAX_SCHEDULE_DAYS:
        errors.add("end_date", "A schedule can run for one year at most.")
        return
    if not occurrences(details, details.start_date, details.end_date):
        errors.add("weekdays", "None of these days falls between the dates.")


def _enqueue(schedule: RecurringSchedule) -> None:
    from apps.lectures.tasks import generate_schedule_lectures

    institute_id, schedule_id = schedule.institute_id, schedule.pk
    transaction.on_commit(
        lambda: generate_schedule_lectures.delay(institute_id, schedule_id)
    )


def _apply_schedule(schedule: RecurringSchedule, details: ScheduleDetails) -> None:
    schedule.title = details.title.strip()
    schedule.teacher = details.teacher
    schedule.batch = details.batch
    schedule.weekdays = sorted(set(details.weekdays))
    schedule.start_time = details.start_time
    schedule.time_zone = details.time_zone
    schedule.duration_minutes = details.duration_minutes
    schedule.start_date = details.start_date
    schedule.end_date = details.end_date
    schedule.delivery_mode = details.delivery_mode
    schedule.description = details.description.strip()
    provider = provider_for(details.delivery_mode)
    schedule.meeting_url = provider.create_meeting(None, details.meeting_url)
    schedule.save()
    schedule.subjects.set(details.subjects)


def preview_schedule(
    institute: Institute,
    details: ScheduleDetails,
    schedule: RecurringSchedule | None = None,
    now: datetime | None = None,
) -> SchedulePreview:
    """The lectures a save would make now, and how many come later.

    Checks the details first (raises ValidationError like a save)."""
    require_tenant_context(institute)
    now = now or timezone.now()
    _check_schedule(institute, details, schedule, now)
    first, last = _window(institute, details, now)
    replaced = _future_lectures(schedule, now) if schedule is not None else None
    planned = _plan(details, occurrences(details, first, last), now, replaced)
    after = max(first, last + timedelta(days=1))
    later = occurrences(details, after, details.end_date)
    return SchedulePreview(planned, len(later), horizon_weeks(institute))


@transaction.atomic
def create_schedule(
    institute: Institute, details: ScheduleDetails
) -> RecurringSchedule:
    """Save the schedule; a task then makes its lectures up to the horizon."""
    require_tenant_context(institute)
    _lock_teacher(details.teacher)
    _check_schedule(institute, details, None, timezone.now())
    schedule = RecurringSchedule(institute=institute)
    _apply_schedule(schedule, details)
    _enqueue(schedule)
    return schedule


@transaction.atomic
def update_schedule(schedule: RecurringSchedule, details: ScheduleDetails) -> int:
    """ "This and all future": lectures not started yet are made again from the
    new details. Lectures edited on their own stay. Returns how many lectures
    were removed for remaking."""
    require_tenant_context(schedule.institute)
    _lock_teacher(details.teacher)
    _lock_and_reload(schedule)
    now = timezone.now()
    _check_schedule(schedule.institute, details, schedule, now)
    # delete() also counts the subject links, so count the lectures alone.
    _, deleted = _future_lectures(schedule, now).delete()
    removed = deleted.get(Lecture._meta.label, 0)
    schedule.generated_until = None
    _apply_schedule(schedule, details)
    _enqueue(schedule)
    return removed


@transaction.atomic
def extend_schedule(schedule: RecurringSchedule, end_date: date) -> None:
    require_tenant_context(schedule.institute)
    _lock_and_reload(schedule)
    errors = _Errors()
    if schedule.status != ScheduleStatus.ACTIVE:
        errors.add("__all__", "A stopped schedule cannot be extended.")
    elif end_date <= schedule.end_date:
        errors.add("end_date", "Choose a date after the current end date.")
    elif (end_date - schedule.start_date).days >= MAX_SCHEDULE_DAYS:
        errors.add("end_date", "A schedule can run for one year at most.")
    errors.raise_any()
    schedule.end_date = end_date
    schedule.save(update_fields=["end_date", "updated_at"])
    _enqueue(schedule)


@transaction.atomic
def stop_schedule(schedule: RecurringSchedule) -> int:
    """No more lectures; the ones not started yet are cancelled (they stay in
    the lists as Cancelled). Returns how many were cancelled."""
    require_tenant_context(schedule.institute)
    _lock_and_reload(schedule)
    schedule.status = ScheduleStatus.STOPPED
    schedule.save(update_fields=["status", "updated_at"])
    return Lecture.objects.filter(
        schedule=schedule,
        status=LectureStatus.SCHEDULED,
        starts_at__gt=timezone.now(),
    ).update(status=LectureStatus.CANCELLED)


def _still_valid(schedule: RecurringSchedule) -> bool:
    """The teacher is active and still teaches every subject in the batch."""
    if schedule.teacher.status != ProfileStatus.ACTIVE:
        return False
    taught = set(
        TeacherBatchSubject.objects.filter(
            teacher=schedule.teacher, batch=schedule.batch
        ).values_list("subject_id", flat=True)
    )
    return all(subject.pk in taught for subject in schedule.subjects.all())


@dataclass(frozen=True)
class GenerateResult:
    created: int = 0
    skipped: int = 0  # the teacher was busy, or the schedule no longer fits


@transaction.atomic
def generate_lectures(
    schedule: RecurringSchedule, now: datetime | None = None
) -> GenerateResult:
    """Make the schedule's lectures up to the horizon. Safe to run again:
    a date that already has a lecture of this schedule is left alone."""
    require_tenant_context(schedule.institute)
    now = now or timezone.now()
    _lock_teacher(schedule.teacher)
    _lock_and_reload(schedule)
    if schedule.status != ScheduleStatus.ACTIVE:
        return GenerateResult()
    first, last = _window(schedule.institute, schedule, now, schedule.generated_until)
    starts = occurrences(schedule, first, last)
    if not _still_valid(schedule):
        return GenerateResult(skipped=len(starts))
    taken = _taken_dates(schedule)
    subjects = list(schedule.subjects.all())
    created = skipped = 0
    for item in _plan(schedule, starts, now):
        if item.starts_at.date() in taken:
            continue
        if item.clash is not None:
            skipped += 1
            continue
        _make_lecture(schedule, item.starts_at, subjects)
        created += 1
    if first <= last:
        schedule.generated_until = last
        schedule.save(update_fields=["generated_until", "updated_at"])
    return GenerateResult(created=created, skipped=skipped)


def _taken_dates(schedule: RecurringSchedule) -> set[date]:
    """Schedule dates that already have a lecture. A lecture moved on its own
    still stands for its first date (``occurrence_date``), so that date is
    not made again and the date it moved to keeps its own lecture."""
    zone = ZoneInfo(schedule.time_zone)
    return {
        lecture.occurrence_date or timezone.localtime(lecture.starts_at, zone).date()
        for lecture in Lecture.objects.filter(schedule=schedule).only(
            "starts_at", "occurrence_date"
        )
    }


def _make_lecture(
    schedule: RecurringSchedule, starts_at: datetime, subjects: list[Subject]
) -> None:
    lecture = Lecture(
        institute=schedule.institute,
        schedule=schedule,
        occurrence_date=starts_at.date(),  # starts_at is in the schedule's zone
        title=schedule.title,
        teacher=schedule.teacher,
        batch=schedule.batch,
        starts_at=starts_at,
        duration_minutes=schedule.duration_minutes,
        delivery_mode=schedule.delivery_mode,
        meeting_url=schedule.meeting_url,
        description=schedule.description,
    )
    lecture.save()
    lecture.subjects.set(subjects)


def list_schedules(
    user: Any, *, teacher_id: int | None = None, batch_id: int | None = None
) -> QuerySet:
    schedules = (
        RecurringSchedule.objects.for_user(user)
        .select_related("teacher__user", "batch")
        .prefetch_related("subjects")
        .annotate(lecture_count=Count("lectures"))
    )
    if teacher_id is not None:
        schedules = schedules.filter(teacher_id=teacher_id)
    if batch_id is not None:
        schedules = schedules.filter(batch_id=batch_id)
    return schedules.order_by("status", "title", "pk")
