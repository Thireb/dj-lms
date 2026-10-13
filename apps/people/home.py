"""Portal home data for teachers, students and guardians (roadmap R4c).

Only what exists now: the person, their batches and subjects, and the
children a guardian is linked to. Lectures (Phase 3), attendance, homework
and fees are added to these pages by their phases.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from apps.academics.models import StudentBatchSubject, TeacherBatchSubject
from apps.people.models import (
    GuardianProfile,
    ProfileStatus,
    StudentProfile,
    TeacherProfile,
)


@dataclass(frozen=True)
class TeacherHome:
    profile: TeacherProfile | None
    pairs: list[str]
    student_count: int
    batch_count: int
    subject_count: int


@dataclass(frozen=True)
class StudentHome:
    profile: StudentProfile | None
    pairs: list[str]


@dataclass(frozen=True)
class GuardianHome:
    profile: GuardianProfile | None
    children: list[StudentProfile]


def greeting(now: datetime) -> str:
    """Good morning (before 12), afternoon (before 17) or evening."""
    if now.hour < 12:
        return "Good morning"
    if now.hour < 17:
        return "Good afternoon"
    return "Good evening"


def _links(queryset: Any) -> list[Any]:
    return list(
        queryset.select_related("batch", "subject").order_by(
            "batch__name", "subject__name"
        )
    )


def _pairs(links: list[Any]) -> list[str]:
    """'Batch: Subject' labels, sorted by batch, then subject."""
    return [f"{link.batch.name}: {link.subject.name}" for link in links]


def teacher_home(user: Any) -> TeacherHome:
    links = _links(TeacherBatchSubject.objects.for_user(user))
    students = StudentProfile.objects.for_user(user).filter(status=ProfileStatus.ACTIVE)
    return TeacherHome(
        profile=TeacherProfile.objects.for_user(user).select_related("user").first(),
        pairs=_pairs(links),
        student_count=students.count(),
        batch_count=len({link.batch_id for link in links}),
        subject_count=len({link.subject_id for link in links}),
    )


def student_home(user: Any) -> StudentHome:
    profile = (
        StudentProfile.objects.for_user(user)
        .select_related("user", "class_label")
        .first()
    )
    return StudentHome(
        profile=profile,
        pairs=_pairs(_links(StudentBatchSubject.objects.for_user(user))),
    )


def guardian_home(user: Any) -> GuardianHome:
    children = (
        StudentProfile.objects.for_user(user)
        .select_related("user", "class_label")
        .prefetch_related("batch_subjects__batch")
        .order_by("user__first_name", "user__last_name", "pk")
    )
    return GuardianHome(
        profile=GuardianProfile.objects.for_user(user).select_related("user").first(),
        children=list(children),
    )
