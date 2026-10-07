"""Profile creation and per-institute ID codes (STU-001, TCH-001)."""

from __future__ import annotations

from typing import Any

from django.db import transaction

from apps.accounts.models import User
from apps.core.tenancy import get_current_institute
from apps.institutes.models import Institute
from apps.people.models import (
    CodeSequence,
    GuardianProfile,
    StudentProfile,
    TeacherProfile,
)

STUDENT_CODE_PREFIX = "STU"
TEACHER_CODE_PREFIX = "TCH"


class TenantContextError(RuntimeError):
    """Raised when a service runs outside the institute it writes to."""


def _require_context(institute: Institute | None) -> None:
    current = get_current_institute()
    if institute is None or current is None or current.pk != institute.pk:
        msg = "Run inside tenant_context() for this institute."
        raise TenantContextError(msg)


def next_code(institute: Institute, prefix: str) -> str:
    """Return the next code for the prefix. Numbers are never reused."""
    _require_context(institute)
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
    _require_context(user.institute)
    return GuardianProfile.objects.create(institute=user.institute, user=user)
