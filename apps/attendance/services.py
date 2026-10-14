"""Mark and read attendance (roadmap 4.1 to 4.3, SPEC 6.3).

A student is expected in a finished lecture when an enrolment of theirs has
the lecture's batch and one of its subjects, and was made before the
lecture ended. A student who already has a mark is expected too, so a mark
stays counted after the enrolment is removed. An expected student with no
mark counts as absent in the percentage and shows as "Not marked".
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.academics.models import StudentBatchSubject
from apps.attendance.models import Attendance, AttendanceSource, AttendanceStatus
from apps.lectures.models import Lecture, LectureStatus
from apps.people.models import StudentProfile

STATUS_KEYS = {key for key, _ in AttendanceStatus.choices}
HALF = Decimal("0.5")


@dataclass(frozen=True)
class Enrolment:
    student_id: int
    batch_id: int
    subject_id: int
    enrolled_at: datetime


def _enrolments(rows: Any) -> list[Enrolment]:
    return [
        Enrolment(*values)
        for values in rows.values_list(
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
