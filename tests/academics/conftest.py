"""A small fake school for academics tests. Fake names only."""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from apps.academics.models import Batch, ClassLabel, Subject
from apps.academics.services import (
    set_student_batch_subjects,
    set_teacher_batch_subjects,
)
from apps.core.tenancy import tenant_context
from apps.institutes.models import Institute
from apps.people.models import GuardianProfile, StudentProfile, TeacherProfile
from apps.people.services import enrol_guardian

from tests.conftest import TEST_LOGIN_PASSWORD
from tests.people.conftest import student, teacher


def make_lists(institute: Institute, model, *names: str) -> list:
    with tenant_context(institute):
        return [model.objects.create(institute=institute, name=n) for n in names]


def link_student(profile: StudentProfile, selections: dict) -> None:
    with tenant_context(profile.institute):
        set_student_batch_subjects(profile, selections)


def link_teacher(profile: TeacherProfile, selections: dict) -> None:
    with tenant_context(profile.institute):
        set_teacher_batch_subjects(profile, selections)


def link_guardian(profile: StudentProfile, email: str) -> GuardianProfile:
    with tenant_context(profile.institute):
        return enrol_guardian(
            profile, email=email, password=TEST_LOGIN_PASSWORD
        ).guardian


@dataclass
class School:
    morning: Batch
    evening: Batch
    math: Subject
    physics: Subject
    grade_9: ClassLabel
    teacher_1: TeacherProfile
    teacher_2: TeacherProfile
    teacher_idle: TeacherProfile
    student_1: StudentProfile
    student_2: StudentProfile
    student_new: StudentProfile
    guardian_1: GuardianProfile
    guardian_2: GuardianProfile
    batch_b: Batch
    teacher_b: TeacherProfile
    student_b: StudentProfile


@pytest.fixture
def school(institute_a: Institute, institute_b: Institute) -> School:
    """Institute A: teacher_1 teaches Morning/Math, teacher_2 Evening/Physics.

    student_1 is in Morning (Math and Physics), student_2 in Evening
    (Physics), student_new has no batch. Institute B mirrors Morning/Math.
    """
    morning, evening = make_lists(institute_a, Batch, "Morning", "Evening")
    math, physics = make_lists(institute_a, Subject, "Math", "Physics")
    (grade_9,) = make_lists(institute_a, ClassLabel, "Grade 9")
    (batch_b,) = make_lists(institute_b, Batch, "Morning")
    (math_b,) = make_lists(institute_b, Subject, "Math")

    teacher_1 = teacher(institute_a, "t1-a@example.com")
    teacher_2 = teacher(institute_a, "t2-a@example.com")
    teacher_idle = teacher(institute_a, "t3-a@example.com")
    teacher_b = teacher(institute_b, "t1-b@example.com")
    link_teacher(teacher_1, {morning: [math]})
    link_teacher(teacher_2, {evening: [physics]})
    link_teacher(teacher_b, {batch_b: [math_b]})

    student_1 = student(institute_a, "s1-a@example.com")
    student_2 = student(institute_a, "s2-a@example.com")
    student_new = student(institute_a, "s3-a@example.com")
    student_b = student(institute_b, "s1-b@example.com")
    link_student(student_1, {morning: [math, physics]})
    link_student(student_2, {evening: [physics]})
    link_student(student_b, {batch_b: [math_b]})

    return School(
        morning=morning,
        evening=evening,
        math=math,
        physics=physics,
        grade_9=grade_9,
        teacher_1=teacher_1,
        teacher_2=teacher_2,
        teacher_idle=teacher_idle,
        student_1=student_1,
        student_2=student_2,
        student_new=student_new,
        guardian_1=link_guardian(student_1, "g1-a@example.com"),
        guardian_2=link_guardian(student_2, "g2-a@example.com"),
        batch_b=batch_b,
        teacher_b=teacher_b,
        student_b=student_b,
    )
