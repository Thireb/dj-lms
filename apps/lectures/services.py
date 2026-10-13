"""Create, edit and list lectures (roadmap 3.1, SPEC 4.5 and 6.4)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import DateTimeField, DurationField, ExpressionWrapper, F
from django.utils import timezone

from apps.academics.models import Batch, Subject, TeacherBatchSubject
from apps.core.tenancy import require_tenant_context
from apps.institutes.models import Institute
from apps.lectures.models import (
    MAX_DURATION,
    MIN_DURATION,
    DeliveryMode,
    Lecture,
    LectureQuerySet,
    LectureStatus,
    meeting_url_validator,
)
from apps.lectures.providers import provider_for
from apps.lectures.times import local_date, local_day_bounds, time_range
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
    require_tenant_context(lecture.institute)
    _lock_teacher(details.teacher)
    _check(lecture.institute, details, lecture)
    return _apply(lecture, details)


def list_lectures(
    user: Any,
    *,
    show: str = SHOW_UPCOMING,
    teacher_id: int | None = None,
    batch_id: int | None = None,
    subject_id: int | None = None,
    status: str = "",
    now: datetime | None = None,
) -> LectureQuerySet:
    """Lectures the user may see, for the Today, Upcoming, Past or All view."""
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
    if status in LectureStatus.values:
        lectures = lectures.filter(status=status)
    if show == "today":
        start, end = local_day_bounds(now)
        lectures = lectures.filter(starts_at__gte=start, starts_at__lt=end)
    elif show == "past":
        return lectures.filter(ends_at_db__lte=now).order_by("-starts_at", "-pk")
    elif show == SHOW_UPCOMING:
        lectures = lectures.filter(ends_at_db__gt=now)
    return lectures.order_by("starts_at", "pk")
