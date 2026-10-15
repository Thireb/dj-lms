"""Assignments (roadmap 5.1, SPEC 4.16 and 6.8).

A teacher publishes an assignment to one batch and subject. Each student
enrolled in that batch and subject sends one text answer before the due
time, and the teacher grades it with marks and feedback.

No submission row means "pending" before the due time and "missed" after
it. A row without marks is "submitted"; a row with marks is "graded".
"""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F

from apps.core.managers import TenantManager, TenantQuerySet, UnscopedTenantManager
from apps.core.models import TenantModel
from apps.core.roles import INSTITUTE_WIDE_ROLES, Role, user_role

MAX_TOTAL_MARKS = 1000

# A student or guardian sees an assignment only through an enrolment in its
# batch and subject. Both conditions sit in one filter() call, so they must
# hold on the same enrolment row (the same rule as lectures).
_ENROLMENT = "subject__student_links__"
STUDENT_LOOKUPS = {
    Role.STUDENT: f"{_ENROLMENT}student__user_id",
    Role.GUARDIAN: f"{_ENROLMENT}student__guardian_links__guardian__user_id",
}

# From a submission to the user who may see it, by role.
SUBMISSION_LOOKUPS = {
    Role.TEACHER: "assignment__teacher__user_id",
    Role.STUDENT: "student__user_id",
    Role.GUARDIAN: "student__guardian_links__guardian__user_id",
}


class SubmissionStatus(models.TextChoices):
    """SPEC 2. Not stored: it comes from the row and the due time."""

    PENDING = "pending", "Pending"
    SUBMITTED = "submitted", "Submitted"
    GRADED = "graded", "Graded"
    MISSED = "missed", "Missed"


class AssignmentQuerySet(TenantQuerySet):
    """Admins see the institute, a teacher their own assignments, a student
    or guardian the assignments of their (child's) batch and subject."""

    def for_user(self, user: Any) -> AssignmentQuerySet:
        scoped = super().for_user(user)
        role = user_role(user)
        user_id = getattr(user, "pk", None)
        if role in INSTITUTE_WIDE_ROLES:
            return scoped
        if role == Role.TEACHER:
            return scoped.filter(teacher__user_id=user_id)
        lookup = STUDENT_LOOKUPS.get(role or "")
        if lookup is None:
            return scoped.none()
        return scoped.filter(
            **{lookup: user_id, f"{_ENROLMENT}batch_id": F("batch_id")}
        ).distinct()


class SubmissionQuerySet(TenantQuerySet):
    """Admins see the institute, a teacher the answers to their own
    assignments, a student their own answers, a guardian their children's."""

    def for_user(self, user: Any) -> SubmissionQuerySet:
        scoped = super().for_user(user)
        role = user_role(user)
        if role in INSTITUTE_WIDE_ROLES:
            return scoped
        lookup = SUBMISSION_LOOKUPS.get(role or "")
        if lookup is None:
            return scoped.none()
        return scoped.filter(**{lookup: getattr(user, "pk", None)}).distinct()


class SameInstituteMixin:
    """Related rows must belong to the row's institute."""

    same_institute: tuple[str, ...] = ()

    def check_institutes(self) -> None:
        for name in self.same_institute:
            related = getattr(self, name, None)
            if related is not None and related.institute_id != self.institute_id:
                raise ValidationError({name: "Must belong to the same institute."})


class Assignment(SameInstituteMixin, TenantModel):
    title = models.CharField(max_length=200)
    instructions = models.TextField()
    teacher = models.ForeignKey(
        "people.TeacherProfile", on_delete=models.PROTECT, related_name="assignments"
    )
    batch = models.ForeignKey(
        "academics.Batch", on_delete=models.PROTECT, related_name="assignments"
    )
    subject = models.ForeignKey(
        "academics.Subject", on_delete=models.PROTECT, related_name="assignments"
    )
    total_marks = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(MAX_TOTAL_MARKS)]
    )
    due_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TenantManager.from_queryset(AssignmentQuerySet)()
    unscoped = UnscopedTenantManager.from_queryset(AssignmentQuerySet)()

    same_institute = ("teacher", "batch", "subject")

    class Meta:
        ordering = ["-due_at", "-pk"]

    def __str__(self) -> str:
        return self.title

    def clean(self) -> None:
        super().clean()
        self.check_institutes()

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.full_clean(validate_unique=False, validate_constraints=False)
        super().save(*args, **kwargs)


class Submission(SameInstituteMixin, TenantModel):
    """One answer per assignment and student; marks and feedback once the
    teacher grades it."""

    assignment = models.ForeignKey(
        Assignment, on_delete=models.PROTECT, related_name="submissions"
    )
    student = models.ForeignKey(
        "people.StudentProfile",
        on_delete=models.PROTECT,
        related_name="assignment_submissions",
    )
    answer = models.TextField()
    submitted_at = models.DateTimeField()
    marks = models.DecimalField(
        max_digits=5,
        decimal_places=1,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    feedback = models.TextField(blank=True)
    graded_at = models.DateTimeField(null=True, blank=True)
    graded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    objects = TenantManager.from_queryset(SubmissionQuerySet)()
    unscoped = UnscopedTenantManager.from_queryset(SubmissionQuerySet)()

    same_institute = ("assignment", "student")

    class Meta:
        ordering = ["assignment_id", "student_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["assignment", "student"],
                name="submission_assignment_student_unique",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.student} - {self.assignment}"

    @property
    def is_graded(self) -> bool:
        return self.marks is not None

    def clean(self) -> None:
        super().clean()
        self.check_institutes()
        assignment = getattr(self, "assignment", None)
        if (
            self.marks is not None
            and assignment is not None
            and self.marks > assignment.total_marks
        ):
            raise ValidationError({"marks": "Marks are more than the total marks."})

    def save(self, *args: Any, **kwargs: Any) -> None:
        # The fail-closed manager would hide rows from unique checks; the
        # database constraint enforces uniqueness instead.
        self.full_clean(validate_unique=False, validate_constraints=False)
        super().save(*args, **kwargs)
