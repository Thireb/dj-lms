"""Student, teacher and guardian profiles (one-to-one with User)."""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models

from apps.core.managers import TenantManager, TenantQuerySet, UnscopedTenantManager
from apps.core.models import TenantModel
from apps.core.roles import Role, user_role

# Roles that see every profile in their own institute (ARCHITECTURE.md section 4).
INSTITUTE_WIDE_ROLES = frozenset(
    {Role.SUPER_ADMIN, Role.INSTITUTE_ADMIN, Role.SUB_ADMIN}
)

cnic_validator = RegexValidator(r"^\d{13}$", "CNIC must be exactly 13 digits.")


class ProfileStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    INACTIVE = "inactive", "Inactive"


class Gender(models.TextChoices):
    MALE = "male", "Male"
    FEMALE = "female", "Female"
    OTHER = "other", "Other"


class OwnProfileQuerySet(TenantQuerySet):
    """Admins see the institute; the profile's own user sees only their row.

    Every other role sees nothing until its link exists: teachers reach
    students through batches (roadmap 2.3), guardians through links (2.2).
    """

    own_role: str = ""

    def for_user(self, user: Any) -> OwnProfileQuerySet:
        scoped = super().for_user(user)
        role = user_role(user)
        if role in INSTITUTE_WIDE_ROLES:
            return scoped
        if role == self.own_role:
            return scoped.filter(user_id=getattr(user, "pk", None))
        return scoped.none()


class StudentProfileQuerySet(OwnProfileQuerySet):
    own_role = Role.STUDENT


class TeacherProfileQuerySet(OwnProfileQuerySet):
    own_role = Role.TEACHER


class GuardianProfileQuerySet(OwnProfileQuerySet):
    own_role = Role.GUARDIAN


class CodeSequence(TenantModel):
    """Last number used for an ID prefix in one institute. Never goes down."""

    prefix = models.CharField(max_length=8)
    last_number = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["institute", "prefix"], name="people_codesequence_unique"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.prefix} at {self.last_number}"


class ProfileBase(TenantModel):
    """Shared checks: the user has the right role and the same institute."""

    profile_role: str = ""

    class Meta:
        abstract = True

    def clean(self) -> None:
        super().clean()
        user = getattr(self, "user", None)
        if user is None:
            return
        if user.role != self.profile_role:
            raise ValidationError(
                {"user": f"User must have the {self.profile_role} role."}
            )
        if user.institute_id != self.institute_id:
            raise ValidationError({"user": "User must belong to the same institute."})

    def save(self, *args: Any, **kwargs: Any) -> None:
        # The default manager is fail-closed, so Django's unique checks would
        # see no rows; the database constraints enforce uniqueness instead.
        self.full_clean(validate_unique=False, validate_constraints=False)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.user.get_full_name() or self.user.email


class StudentProfile(ProfileBase):
    profile_role = Role.STUDENT

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="student_profile",
    )
    student_code = models.CharField(max_length=16)
    father_name = models.CharField(max_length=150, blank=True, default="")
    cnic = models.CharField(
        "CNIC", max_length=13, blank=True, default="", validators=[cnic_validator]
    )
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(
        max_length=8, choices=Gender.choices, blank=True, default=""
    )
    guardian_phone = models.CharField(max_length=32)
    address = models.TextField(blank=True, default="")
    city = models.CharField(max_length=100, blank=True, default="")
    status = models.CharField(
        max_length=8, choices=ProfileStatus.choices, default=ProfileStatus.ACTIVE
    )
    created_at = models.DateTimeField(auto_now_add=True)

    objects = TenantManager.from_queryset(StudentProfileQuerySet)()
    unscoped = UnscopedTenantManager.from_queryset(StudentProfileQuerySet)()

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["institute", "student_code"],
                name="people_student_code_unique",
            ),
        ]


class TeacherProfile(ProfileBase):
    profile_role = Role.TEACHER

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="teacher_profile",
    )
    teacher_code = models.CharField(max_length=16)
    cnic = models.CharField(
        "CNIC", max_length=13, blank=True, default="", validators=[cnic_validator]
    )
    address = models.TextField(blank=True, default="")
    joining_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=8, choices=ProfileStatus.choices, default=ProfileStatus.ACTIVE
    )
    created_at = models.DateTimeField(auto_now_add=True)

    objects = TenantManager.from_queryset(TeacherProfileQuerySet)()
    unscoped = UnscopedTenantManager.from_queryset(TeacherProfileQuerySet)()

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["institute", "teacher_code"],
                name="people_teacher_code_unique",
            ),
        ]


class GuardianProfile(ProfileBase):
    profile_role = Role.GUARDIAN

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="guardian_profile",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    objects = TenantManager.from_queryset(GuardianProfileQuerySet)()
    unscoped = UnscopedTenantManager.from_queryset(GuardianProfileQuerySet)()

    class Meta:
        ordering = ["-created_at"]
