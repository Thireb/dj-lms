"""Attendance (roadmap 4.1, SPEC 6.3): one row per lecture per student.

No row means "not marked". Only finished lectures take marks.
"""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.core.managers import TenantManager, TenantQuerySet, UnscopedTenantManager
from apps.core.models import TenantModel
from apps.core.roles import INSTITUTE_WIDE_ROLES, Role, user_role

# From an attendance row to the user who may see it, by role.
ROLE_LOOKUPS = {
    Role.TEACHER: "lecture__teacher__user_id",
    Role.STUDENT: "student__user_id",
    Role.GUARDIAN: "student__guardian_links__guardian__user_id",
}


class AttendanceStatus(models.TextChoices):
    PRESENT = "present", "Present"
    PARTIAL = "partial", "Partial"
    LATE = "late", "Late"
    ABSENT = "absent", "Absent"


class AttendanceSource(models.TextChoices):
    MANUAL = "manual", "Manual"
    PROVIDER = "provider", "Meeting provider"


class AttendanceQuerySet(TenantQuerySet):
    """Admins see the institute, a teacher the rows of their own lectures, a
    student their own rows, a guardian the rows of their linked children."""

    def for_user(self, user: Any) -> AttendanceQuerySet:
        scoped = super().for_user(user)
        role = user_role(user)
        if role in INSTITUTE_WIDE_ROLES:
            return scoped
        lookup = ROLE_LOOKUPS.get(role or "")
        if lookup is None:
            return scoped.none()
        return scoped.filter(**{lookup: getattr(user, "pk", None)}).distinct()


class Attendance(TenantModel):
    lecture = models.ForeignKey(
        "lectures.Lecture", on_delete=models.PROTECT, related_name="attendance"
    )
    student = models.ForeignKey(
        "people.StudentProfile", on_delete=models.PROTECT, related_name="attendance"
    )
    status = models.CharField(max_length=16, choices=AttendanceStatus.choices)
    source = models.CharField(
        max_length=16,
        choices=AttendanceSource.choices,
        default=AttendanceSource.MANUAL,
    )
    marked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    marked_at = models.DateTimeField(auto_now=True)

    objects = TenantManager.from_queryset(AttendanceQuerySet)()
    unscoped = UnscopedTenantManager.from_queryset(AttendanceQuerySet)()

    class Meta:
        ordering = ["lecture_id", "student_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["lecture", "student"], name="attendance_lecture_student_unique"
            ),
        ]
        verbose_name_plural = "attendance"

    def __str__(self) -> str:
        return f"{self.student} - {self.lecture}: {self.get_status_display()}"

    def clean(self) -> None:
        super().clean()
        for name in ("lecture", "student"):
            related = getattr(self, name, None)
            if related is not None and related.institute_id != self.institute_id:
                raise ValidationError({name: "Must belong to the same institute."})

    def save(self, *args: Any, **kwargs: Any) -> None:
        # The fail-closed manager would hide rows from unique checks; the
        # database constraint enforces uniqueness instead.
        self.full_clean(validate_unique=False, validate_constraints=False)
        super().save(*args, **kwargs)
