"""Class labels, batches, subjects, and the links made on people.

ClassLabel, Batch and Subject are independent name lists. Students and
teachers are linked to (batch, subject) pairs; there is no other link.
"""

from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.functions import Lower

from apps.core.managers import TenantManager, TenantQuerySet, UnscopedTenantManager
from apps.core.models import TenantModel
from apps.core.roles import INSTITUTE_WIDE_ROLES, Role, user_role

# Lookups from a batch or subject row to the user who may see it, by role.
LIST_LOOKUPS = {
    Role.TEACHER: "teacher_links__teacher__user_id",
    Role.STUDENT: "student_links__student__user_id",
    Role.GUARDIAN: "student_links__student__guardian_links__guardian__user_id",
}

# Students: a teacher sees every enrolment in the batches they teach.
STUDENT_LINK_LOOKUPS = {
    Role.TEACHER: "batch__teacher_links__teacher__user_id",
    Role.STUDENT: "student__user_id",
    Role.GUARDIAN: "student__guardian_links__guardian__user_id",
}

# Teachers: students and guardians see the teachers of their batches.
TEACHER_LINK_LOOKUPS = {
    Role.TEACHER: "teacher__user_id",
    Role.STUDENT: "batch__student_links__student__user_id",
    Role.GUARDIAN: "batch__student_links__student__guardian_links__guardian__user_id",
}


class RoleLookupQuerySet(TenantQuerySet):
    """Admins see the institute; other roles follow ``role_lookups``."""

    role_lookups: dict[str, str] = {}

    def for_user(self, user: Any) -> RoleLookupQuerySet:
        scoped = super().for_user(user)
        role = user_role(user)
        if role in INSTITUTE_WIDE_ROLES:
            return scoped
        lookup = self.role_lookups.get(role or "")
        if lookup is None:
            return scoped.none()
        return scoped.filter(**{lookup: getattr(user, "pk", None)}).distinct()


class ClassLabelQuerySet(RoleLookupQuerySet):
    """Labels are an admin list; people read their own label from the profile."""


class BatchSubjectQuerySet(RoleLookupQuerySet):
    role_lookups = LIST_LOOKUPS


class StudentBatchSubjectQuerySet(RoleLookupQuerySet):
    role_lookups = STUDENT_LINK_LOOKUPS


class TeacherBatchSubjectQuerySet(RoleLookupQuerySet):
    role_lookups = TEACHER_LINK_LOOKUPS


class NameList(TenantModel):
    """A name-only list row. Names are unique per institute, ignoring case."""

    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                Lower("name"),
                "institute",
                name="%(app_label)s_%(class)s_name_unique",
            ),
        ]

    def __str__(self) -> str:
        return self.name


class ClassLabel(NameList):
    objects = TenantManager.from_queryset(ClassLabelQuerySet)()
    unscoped = UnscopedTenantManager.from_queryset(ClassLabelQuerySet)()

    class Meta(NameList.Meta):
        pass


class Batch(NameList):
    objects = TenantManager.from_queryset(BatchSubjectQuerySet)()
    unscoped = UnscopedTenantManager.from_queryset(BatchSubjectQuerySet)()

    class Meta(NameList.Meta):
        verbose_name_plural = "batches"


class Subject(NameList):
    objects = TenantManager.from_queryset(BatchSubjectQuerySet)()
    unscoped = UnscopedTenantManager.from_queryset(BatchSubjectQuerySet)()

    class Meta(NameList.Meta):
        pass


class BatchSubjectLink(TenantModel):
    """A person linked to one (batch, subject) pair in the same institute."""

    person_field: str = ""

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True

    def clean(self) -> None:
        super().clean()
        for name in (self.person_field, "batch", "subject"):
            related = getattr(self, name, None)
            if related is not None and related.institute_id != self.institute_id:
                raise ValidationError({name: "Must belong to the same institute."})

    def save(self, *args: Any, **kwargs: Any) -> None:
        # The default manager is fail-closed, so Django's unique checks would
        # see no rows; the database constraints enforce uniqueness instead.
        self.full_clean(validate_unique=False, validate_constraints=False)
        super().save(*args, **kwargs)


class StudentBatchSubject(BatchSubjectLink):
    person_field = "student"

    student = models.ForeignKey(
        "people.StudentProfile",
        on_delete=models.PROTECT,
        related_name="batch_subjects",
    )
    batch = models.ForeignKey(
        Batch, on_delete=models.PROTECT, related_name="student_links"
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.PROTECT, related_name="student_links"
    )

    objects = TenantManager.from_queryset(StudentBatchSubjectQuerySet)()
    unscoped = UnscopedTenantManager.from_queryset(StudentBatchSubjectQuerySet)()

    class Meta:
        ordering = ["batch__name", "subject__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["student", "batch", "subject"],
                name="academics_student_batch_subject_unique",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.student} - {self.batch} / {self.subject}"


class TeacherBatchSubject(BatchSubjectLink):
    person_field = "teacher"

    teacher = models.ForeignKey(
        "people.TeacherProfile",
        on_delete=models.PROTECT,
        related_name="batch_subjects",
    )
    batch = models.ForeignKey(
        Batch, on_delete=models.PROTECT, related_name="teacher_links"
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.PROTECT, related_name="teacher_links"
    )

    objects = TenantManager.from_queryset(TeacherBatchSubjectQuerySet)()
    unscoped = UnscopedTenantManager.from_queryset(TeacherBatchSubjectQuerySet)()

    class Meta:
        ordering = ["batch__name", "subject__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["teacher", "batch", "subject"],
                name="academics_teacher_batch_subject_unique",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.teacher} - {self.batch} / {self.subject}"
