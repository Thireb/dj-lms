"""Profiles, per-institute ID codes (STU-001, TCH-001) and guardian links."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction

from apps.accounts.models import User
from apps.core.roles import Role
from apps.core.tenancy import require_tenant_context
from apps.institutes.models import Institute
from apps.people.models import (
    CodeSequence,
    GuardianProfile,
    GuardianStudentLink,
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


GUARDIAN_EMAIL_TAKEN = "This email is already used by another account."


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
        raise ValidationError({"guardian_email": GUARDIAN_EMAIL_TAKEN})
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
