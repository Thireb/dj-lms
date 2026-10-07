"""Profiles, ID codes (STU-001, TCH-001), guardian links and teacher accounts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Prefetch, Q, QuerySet

from apps.academics.models import TeacherBatchSubject
from apps.academics.services import Selections, set_teacher_batch_subjects
from apps.accounts.models import User
from apps.core.roles import Role
from apps.core.tenancy import require_tenant_context
from apps.institutes.models import Institute
from apps.people.models import (
    CodeSequence,
    GuardianProfile,
    GuardianStudentLink,
    ProfileStatus,
    StudentProfile,
    TeacherProfile,
)

STUDENT_CODE_PREFIX = "STU"
TEACHER_CODE_PREFIX = "TCH"


def next_code(institute: Institute, prefix: str) -> str:
    """Return the next code for the prefix. Numbers are never reused."""
    require_tenant_context(institute)
    with transaction.atomic():
        sequence, _ = CodeSequence.objects.select_for_update().get_or_create(
            institute=institute, prefix=prefix
        )
        sequence.last_number += 1
        sequence.save(update_fields=["last_number"])
    return f"{prefix}-{sequence.last_number:03d}"


@transaction.atomic
def create_student_profile(user: User, **fields: Any) -> StudentProfile:
    institute = user.institute
    code = next_code(institute, STUDENT_CODE_PREFIX)
    return StudentProfile.objects.create(
        institute=institute, user=user, student_code=code, **fields
    )


@transaction.atomic
def create_teacher_profile(user: User, **fields: Any) -> TeacherProfile:
    institute = user.institute
    code = next_code(institute, TEACHER_CODE_PREFIX)
    return TeacherProfile.objects.create(
        institute=institute, user=user, teacher_code=code, **fields
    )


def create_guardian_profile(user: User) -> GuardianProfile:
    require_tenant_context(user.institute)
    return GuardianProfile.objects.create(institute=user.institute, user=user)


EMAIL_TAKEN = "This email is already used by another account."


@dataclass(frozen=True)
class GuardianEnrolment:
    guardian: GuardianProfile
    created: bool


@transaction.atomic
def enrol_guardian(
    student: StudentProfile,
    *,
    email: str,
    password: str,
    first_name: str = "",
    last_name: str = "",
    phone: str = "",
) -> GuardianEnrolment:
    """Link the student to the guardian with this email, creating them if new.

    An existing guardian of the same institute is reused as is: the password,
    name and phone given here are ignored. Any other account with the email
    is an error that does not say which role or institute owns it.
    """
    institute = student.institute
    require_tenant_context(institute)
    email = email.strip().lower()
    existing = User.objects.filter(email__iexact=email).first()
    if existing is None:
        guardian = _create_guardian(
            institute,
            email=email,
            password=password,
            first_name=first_name.strip(),
            last_name=last_name.strip(),
            phone=phone.strip(),
        )
        created = True
    elif _is_guardian_of(existing, institute):
        guardian = GuardianProfile.objects.filter(
            user=existing
        ).first() or create_guardian_profile(existing)
        created = False
    else:
        raise ValidationError({"guardian_email": EMAIL_TAKEN})
    GuardianStudentLink.objects.get_or_create(
        institute=institute, guardian=guardian, student=student
    )
    return GuardianEnrolment(guardian=guardian, created=created)


def _is_guardian_of(user: User, institute: Institute) -> bool:
    is_guardian = user.role == Role.GUARDIAN
    return is_guardian and user.institute_id == institute.pk


def _create_guardian(
    institute: Institute, *, email: str, password: str, **fields: str
) -> GuardianProfile:
    user = User(email=email, role=Role.GUARDIAN, institute=institute, **fields)
    try:
        validate_password(password, user)
    except ValidationError as error:
        raise ValidationError({"guardian_password": error.messages}) from error
    user = User.objects.create_user(
        email=email,
        password=password,
        role=Role.GUARDIAN,
        institute=institute,
        **fields,
    )
    return create_guardian_profile(user)


# Teachers (roadmap 2.5a, SPEC 4.2)


def list_teachers(
    user: object,
    *,
    search: str = "",
    batch_id: int | None = None,
    status: str = "",
) -> QuerySet[TeacherProfile]:
    """The user's teachers, newest first, with links prefetched for the table."""
    teachers = TeacherProfile.objects.for_user(user).select_related("user")
    for term in search.split():
        teachers = teachers.filter(
            Q(user__first_name__icontains=term)
            | Q(user__last_name__icontains=term)
            | Q(user__email__icontains=term)
            | Q(user__phone__icontains=term)
            | Q(teacher_code__icontains=term)
        )
    if batch_id is not None:
        teachers = teachers.filter(batch_subjects__batch_id=batch_id).distinct()
    if status in ProfileStatus.values:
        teachers = teachers.filter(status=status)
    links = TeacherBatchSubject.objects.select_related("batch", "subject")
    return teachers.prefetch_related(
        Prefetch("batch_subjects", queryset=links)
    ).order_by("-created_at", "-pk")


def split_full_name(full_name: str) -> tuple[str, str]:
    """ "Sam A. Sample" -> ("Sam", "A. Sample"); the profile page edits both."""
    parts = " ".join(full_name.split()).split(" ", 1)
    return parts[0], parts[1] if len(parts) > 1 else ""


def _check_email_free(email: str, field: str, user: User | None = None) -> str:
    email = email.strip().lower()
    taken = User.objects.filter(email__iexact=email)
    if user is not None:
        taken = taken.exclude(pk=user.pk)
    if taken.exists():
        raise ValidationError({field: EMAIL_TAKEN})
    return email


def _set_pairs(teacher: TeacherProfile, selections: Selections) -> None:
    try:
        set_teacher_batch_subjects(teacher, selections)
    except ValidationError as error:
        raise ValidationError({"batch_subjects": error.messages}) from error


@transaction.atomic
def create_teacher(
    institute: Institute,
    *,
    full_name: str,
    email: str,
    password: str,
    phone: str,
    selections: Selections,
    cnic: str = "",
    address: str = "",
    joining_date: date | None = None,
) -> TeacherProfile:
    require_tenant_context(institute)
    email = _check_email_free(email, "email")
    first_name, last_name = split_full_name(full_name)
    user = User(
        email=email,
        role=Role.TEACHER,
        institute=institute,
        first_name=first_name,
        last_name=last_name,
        phone=phone.strip(),
    )
    try:
        validate_password(password, user)
    except ValidationError as error:
        raise ValidationError({"password": error.messages}) from error
    user.set_password(password)
    user.save()
    teacher = create_teacher_profile(
        user, cnic=cnic.strip(), address=address.strip(), joining_date=joining_date
    )
    _set_pairs(teacher, selections)
    return teacher


@transaction.atomic
def update_teacher(
    teacher: TeacherProfile,
    *,
    full_name: str,
    email: str,
    phone: str,
    selections: Selections,
    cnic: str = "",
    address: str = "",
    joining_date: date | None = None,
) -> TeacherProfile:
    require_tenant_context(teacher.institute)
    user = teacher.user
    user.email = _check_email_free(email, "email", user=user)
    user.first_name, user.last_name = split_full_name(full_name)
    user.phone = phone.strip()
    user.save()
    teacher.cnic = cnic.strip()
    teacher.address = address.strip()
    teacher.joining_date = joining_date
    teacher.save()
    _set_pairs(teacher, selections)
    return teacher


@transaction.atomic
def set_teacher_active(teacher: TeacherProfile, *, is_active: bool) -> TeacherProfile:
    """Status and sign-in change together: an inactive teacher cannot sign in."""
    require_tenant_context(teacher.institute)
    teacher.status = ProfileStatus.ACTIVE if is_active else ProfileStatus.INACTIVE
    teacher.save(update_fields=["status"])
    teacher.user.is_active = is_active
    teacher.user.save(update_fields=["is_active"])
    return teacher
