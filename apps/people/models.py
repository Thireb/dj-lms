"""Student, teacher and guardian profiles (one-to-one with User)."""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models

from apps.core.managers import TenantManager, TenantQuerySet, UnscopedTenantManager
from apps.core.models import TenantModel
from apps.core.roles import INSTITUTE_WIDE_ROLES, Role, user_role

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

    Other roles see a profile only through a link (``for_linked_role``):
    guardian links (people) or shared batches (academics).
    """

    own_role: str = ""

    def for_user(self, user: Any) -> OwnProfileQuerySet:
        scoped = super().for_user(user)
        role = user_role(user)
        user_id = getattr(user, "pk", None)
        if role in INSTITUTE_WIDE_ROLES:
            return scoped
        if role == self.own_role:
            return scoped.filter(user_id=user_id)
        return scoped.for_linked_role(role, user_id)

    def for_linked_role(self, role: str | None, user_id: Any) -> OwnProfileQuerySet:
        return self.none()


class StudentProfileQuerySet(OwnProfileQuerySet):
    own_role = Role.STUDENT

    def for_linked_role(self, role: str | None, user_id: Any) -> OwnProfileQuerySet:
        if role == Role.GUARDIAN:
            return self.filter(guardian_links__guardian__user_id=user_id)
        if role == Role.TEACHER:
            # Every student enrolled in a batch the teacher teaches.
            return self.filter(
                batch_subjects__batch__teacher_links__teacher__user_id=user_id
            ).distinct()
        return self.none()


class TeacherProfileQuerySet(OwnProfileQuerySet):
    own_role = Role.TEACHER

    def for_linked_role(self, role: str | None, user_id: Any) -> OwnProfileQuerySet:
        # Students and guardians see the teachers of their batches.
        students = "batch_subjects__batch__student_links__student__"
        if role == Role.STUDENT:
            return self.filter(**{f"{students}user_id": user_id}).distinct()
        if role == Role.GUARDIAN:
            lookup = f"{students}guardian_links__guardian__user_id"
            return self.filter(**{lookup: user_id}).distinct()
        return self.none()


class GuardianProfileQuerySet(OwnProfileQuerySet):
    own_role = Role.GUARDIAN

    def for_linked_role(self, role: str | None, user_id: Any) -> OwnProfileQuerySet:
        if role == Role.STUDENT:
            return self.filter(student_links__student__user_id=user_id)
        return self.none()


class GuardianStudentLinkQuerySet(TenantQuerySet):
    """Admins see the institute; a guardian or student sees only their links."""

    def for_user(self, user: Any) -> GuardianStudentLinkQuerySet:
        scoped = super().for_user(user)
        role = user_role(user)
        user_id = getattr(user, "pk", None)
        if role in INSTITUTE_WIDE_ROLES:
            return scoped
        if role == Role.GUARDIAN:
            return scoped.filter(guardian__user_id=user_id)
        if role == Role.STUDENT:
            return scoped.filter(student__user_id=user_id)
        return scoped.none()


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
    class_label = models.ForeignKey(
        "academics.ClassLabel",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="students",
    )
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

    def clean(self) -> None:
        super().clean()
        label = self.class_label
        if label is not None and label.institute_id != self.institute_id:
            raise ValidationError({"class_label": "Must belong to the same institute."})

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


class GuardianStudentLink(TenantModel):
    """One guardian linked to one student. A guardian can have many children."""

    guardian = models.ForeignKey(
        GuardianProfile, on_delete=models.PROTECT, related_name="student_links"
    )
    student = models.ForeignKey(
        StudentProfile, on_delete=models.PROTECT, related_name="guardian_links"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    objects = TenantManager.from_queryset(GuardianStudentLinkQuerySet)()
    unscoped = UnscopedTenantManager.from_queryset(GuardianStudentLinkQuerySet)()

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["guardian", "student"], name="people_guardian_student_unique"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.guardian} - {self.student}"

    def clean(self) -> None:
        super().clean()
        for name in ("guardian", "student"):
            profile = getattr(self, name, None)
            if profile is not None and profile.institute_id != self.institute_id:
                raise ValidationError({name: "Must belong to the same institute."})

    def save(self, *args: Any, **kwargs: Any) -> None:
        # Same reason as ProfileBase.save: the database enforces uniqueness.
        self.full_clean(validate_unique=False, validate_constraints=False)
        super().save(*args, **kwargs)


class PortalAccessRuleQuerySet(TenantQuerySet):
    """Admins see the institute; a student sees only their own rule."""

    def for_user(self, user: Any) -> PortalAccessRuleQuerySet:
        scoped = super().for_user(user)
        role = user_role(user)
        if role in INSTITUTE_WIDE_ROLES:
            return scoped
        if role == Role.STUDENT:
            return scoped.filter(student__user_id=getattr(user, "pk", None))
        return scoped.none()


class PortalAccessRule(TenantModel):
    """Student portal access (SPEC 6.2). No row means open and not exempt.

    ``blocked`` closes the student portal; the guardian portal is never
    blocked. ``exempt`` only protects the student from the automatic
    defaulter rule (roadmap 7.6); a manual block still applies.
    """

    student = models.OneToOneField(
        StudentProfile, on_delete=models.PROTECT, related_name="access_rule"
    )
    blocked = models.BooleanField(default=False)
    exempt = models.BooleanField(default=False)
    changed_at = models.DateTimeField(auto_now=True)

    objects = TenantManager.from_queryset(PortalAccessRuleQuerySet)()
    unscoped = UnscopedTenantManager.from_queryset(PortalAccessRuleQuerySet)()

    def __str__(self) -> str:
        return f"Access for {self.student}"

    def clean(self) -> None:
        super().clean()
        student = getattr(self, "student", None)
        if student is not None and student.institute_id != self.institute_id:
            raise ValidationError({"student": "Must belong to the same institute."})

    def save(self, *args: Any, **kwargs: Any) -> None:
        # Same reason as ProfileBase.save: the database enforces uniqueness.
        self.full_clean(validate_unique=False, validate_constraints=False)
        super().save(*args, **kwargs)
