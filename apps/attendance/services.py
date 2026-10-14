"""Mark and read attendance (roadmap 4.1 to 4.3, SPEC 6.3).

A student is expected in a finished lecture when an enrolment of theirs has
the lecture's batch and one of its subjects, and was made before the
lecture ended. A student who already has a mark is expected too, so a mark
stays counted after the enrolment is removed. An expected student with no
mark counts as absent in the percentage and shows as "Not marked".
An inactive student (one who left) is expected only where they have a mark,
so the form does not start them at Present.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.dateformat import format as date_format

from apps.academics.models import StudentBatchSubject
from apps.attendance.models import Attendance, AttendanceSource, AttendanceStatus
from apps.lectures.models import Lecture, LectureStatus
from apps.lectures.times import combine_local
from apps.people.models import ProfileStatus, StudentProfile

STATUS_KEYS = {key for key, _ in AttendanceStatus.choices}
HALF = Decimal("0.5")


@dataclass(frozen=True)
class Enrolment:
    student_id: int
    batch_id: int
    subject_id: int
    enrolled_at: datetime


def _enrolments(rows: Any) -> list[Enrolment]:
    """The enrolments of active students only (see the module text)."""
    active = rows.filter(student__status=ProfileStatus.ACTIVE)
    return [
        Enrolment(*values)
        for values in active.values_list(
            "student_id", "batch_id", "subject_id", "created_at"
        )
    ]


def is_expected(lecture: Lecture, enrolment: Enrolment) -> bool:
    """The enrolment covers this lecture (see the module text)."""
    subject_ids = {subject.pk for subject in lecture.subjects.all()}
    return (
        enrolment.batch_id == lecture.batch_id
        and enrolment.subject_id in subject_ids
        and enrolment.enrolled_at < lecture.ends_at
    )


def can_mark(lecture: Lecture) -> bool:
    """Only a finished lecture takes marks (a not-held one never ran)."""
    return lecture.status == LectureStatus.FINISHED


# One lecture (roadmap 4.1)


@dataclass(frozen=True)
class RosterEntry:
    student: StudentProfile
    status: str  # "" when not marked


def _marks(lecture: Lecture) -> dict[int, str]:
    return dict(
        Attendance.objects.filter(lecture=lecture).values_list("student_id", "status")
    )


def _expected_ids(lecture: Lecture, marks: dict[int, str]) -> set[int]:
    links = StudentBatchSubject.objects.filter(batch_id=lecture.batch_id)
    enrolled = {
        enrolment.student_id
        for enrolment in _enrolments(links)
        if is_expected(lecture, enrolment)
    }
    return enrolled | set(marks)


def roster(lecture: Lecture) -> list[RosterEntry]:
    """The expected students of a lecture by name, with their marks."""
    marks = _marks(lecture)
    students = (
        StudentProfile.objects.filter(pk__in=_expected_ids(lecture, marks))
        .select_related("user")
        .order_by("user__first_name", "user__last_name", "pk")
    )
    return [RosterEntry(student, marks.get(student.pk, "")) for student in students]


def save_marks(lecture: Lecture, marks: dict[int, str], *, marked_by: Any) -> int:
    """Save the teacher's marks (student pk to status); returns how many rows
    changed. Every student must be on the lecture's roster."""
    with transaction.atomic():
        lecture = Lecture.objects.select_for_update().get(pk=lecture.pk)
        if not can_mark(lecture):
            raise ValidationError("Attendance is taken only for a finished lecture.")
        saved = _marks(lecture)
        expected = _expected_ids(lecture, saved)
        if not set(marks) <= expected:
            raise ValidationError("A student is not in this lecture.")
        if not set(marks.values()) <= STATUS_KEYS:
            raise ValidationError("Choose Present, Partial, Late or Absent.")
        changed = 0
        for student_id, status in marks.items():
            if saved.get(student_id) == status:
                continue
            Attendance.objects.update_or_create(
                lecture=lecture,
                student_id=student_id,
                defaults={
                    "institute": lecture.institute,
                    "status": status,
                    "source": AttendanceSource.MANUAL,
                    "marked_by": marked_by,
                },
            )
            changed += 1
    return changed


@dataclass(frozen=True)
class LectureCount:
    attended: int  # present, late or partial
    marked: int
    total: int  # expected students


ATTENDED = {AttendanceStatus.PRESENT, AttendanceStatus.LATE, AttendanceStatus.PARTIAL}


def lecture_counts(lectures: list[Lecture]) -> dict[int, LectureCount]:
    """Present / Total for a page of lectures (Lecture History), in 2
    queries. The lectures need their subjects prefetched."""
    if not lectures:
        return {}
    links = StudentBatchSubject.objects.filter(
        batch_id__in={lecture.batch_id for lecture in lectures}
    )
    enrolments = _enrolments(links)
    marks: dict[int, dict[int, str]] = defaultdict(dict)
    rows = Attendance.objects.filter(lecture__in=lectures).values_list(
        "lecture_id", "student_id", "status"
    )
    for lecture_id, student_id, status in rows:
        marks[lecture_id][student_id] = status
    counts = {}
    for lecture in lectures:
        own = marks[lecture.pk]
        expected = {e.student_id for e in enrolments if is_expected(lecture, e)}
        counts[lecture.pk] = LectureCount(
            attended=sum(1 for status in own.values() if status in ATTENDED),
            marked=len(own),
            total=len(expected | set(own)),
        )
    return counts


# One student (roadmap 4.2 and 4.3)


@dataclass(frozen=True)
class Record:
    lecture: Lecture
    status: str  # "" when not marked


def student_records(
    student: StudentProfile,
    *,
    subject_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[Record]:
    """The finished lectures a student was expected in, newest first, with
    their marks. The caller checks that the viewer may see the student.
    ``date_from`` and ``date_to`` are days in the viewer's zone, both in."""
    enrolments = _enrolments(StudentBatchSubject.objects.filter(student=student))
    marks = dict(
        Attendance.objects.filter(student=student).values_list("lecture_id", "status")
    )
    lectures = (
        Lecture.objects.filter(status=LectureStatus.FINISHED)
        .filter(Q(batch_id__in={e.batch_id for e in enrolments}) | Q(pk__in=marks))
        .select_related("teacher__user", "batch")
        .prefetch_related("subjects")
        .order_by("-starts_at", "-pk")
    )
    if subject_id is not None:
        lectures = lectures.filter(subjects__id=subject_id)
    if date_from is not None:
        lectures = lectures.filter(starts_at__gte=combine_local(date_from, time.min))
    if date_to is not None:
        day_after = date_to + timedelta(days=1)
        lectures = lectures.filter(starts_at__lt=combine_local(day_after, time.min))
    return [
        Record(lecture, marks.get(lecture.pk, ""))
        for lecture in lectures
        if lecture.pk in marks or any(is_expected(lecture, e) for e in enrolments)
    ]


@dataclass(frozen=True)
class Summary:
    present: int = 0
    late: int = 0
    partial: int = 0
    absent: int = 0
    not_marked: int = 0

    @property
    def total(self) -> int:
        return self.present + self.late + self.partial + self.absent + self.not_marked

    @property
    def percent(self) -> Decimal | None:
        """SPEC 6.3: (Present + Late + 0.5 x Partial) / expected lectures,
        to one decimal; None before the first finished lecture."""
        if not self.total:
            return None
        attended = self.present + self.late + HALF * self.partial
        share = attended * 100 / self.total
        return share.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


SUMMARY_FIELDS = {
    AttendanceStatus.PRESENT: "present",
    AttendanceStatus.LATE: "late",
    AttendanceStatus.PARTIAL: "partial",
    AttendanceStatus.ABSENT: "absent",
    "": "not_marked",
}


def summarize(records: list[Record]) -> Summary:
    counts = dict.fromkeys(SUMMARY_FIELDS.values(), 0)
    for record in records:
        counts[SUMMARY_FIELDS[record.status]] += 1
    return Summary(**counts)


# Summaries (roadmap 4.3)


@dataclass(frozen=True)
class GroupSummary:
    label: str
    summary: Summary


def by_month(records: list[Record]) -> list[GroupSummary]:
    """One summary per month in the viewer's zone, newest first."""
    groups: dict[date, list[Record]] = defaultdict(list)
    for record in records:
        day = timezone.localtime(record.lecture.starts_at).date()
        groups[day.replace(day=1)].append(record)
    return [
        GroupSummary(date_format(month, "F Y"), summarize(groups[month]))
        for month in sorted(groups, reverse=True)
    ]


def by_subject(records: list[Record], subject_ids: set[int]) -> list[GroupSummary]:
    """One summary per subject, by name. A lecture with several subjects
    counts for the student's own subjects among them (``subject_ids``), or
    for all of them when the student no longer takes any."""
    groups: dict[str, list[Record]] = defaultdict(list)
    for record in records:
        subjects = list(record.lecture.subjects.all())
        own = [subject for subject in subjects if subject.pk in subject_ids]
        for subject in own or subjects:
            groups[subject.name].append(record)
    return [GroupSummary(name, summarize(groups[name])) for name in sorted(groups)]


def student_subject_ids(student: StudentProfile) -> set[int]:
    links = StudentBatchSubject.objects.filter(student=student)
    return set(links.values_list("subject_id", flat=True))


def student_summaries(students: list[StudentProfile]) -> dict[int, Summary]:
    """Each student's summary of all finished classes (dashboards), in 4
    queries for any number of students."""
    ids = [student.pk for student in students]
    enrolments: dict[int, list[Enrolment]] = defaultdict(list)
    for enrolment in _enrolments(
        StudentBatchSubject.objects.filter(student_id__in=ids)
    ):
        enrolments[enrolment.student_id].append(enrolment)
    marks: dict[int, dict[int, str]] = defaultdict(dict)
    rows = Attendance.objects.filter(student_id__in=ids).values_list(
        "student_id", "lecture_id", "status"
    )
    for student_id, lecture_id, status in rows:
        marks[student_id][lecture_id] = status
    batch_ids = {e.batch_id for own in enrolments.values() for e in own}
    marked_ids = {lecture_id for own in marks.values() for lecture_id in own}
    lectures = list(
        Lecture.objects.filter(status=LectureStatus.FINISHED)
        .filter(Q(batch_id__in=batch_ids) | Q(pk__in=marked_ids))
        .prefetch_related("subjects")
    )
    return {
        pk: summarize(
            [
                Record(lecture, marks[pk].get(lecture.pk, ""))
                for lecture in lectures
                if lecture.pk in marks[pk]
                or any(is_expected(lecture, e) for e in enrolments[pk])
            ]
        )
        for pk in ids
    }
