"""Lectures (roadmap 3.1, SPEC 4.5 and 6.4).

A lecture has one teacher, one batch and one or more subjects. Times are
stored in UTC; pages show them in the viewer's time zone.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, URLValidator
from django.db import models
from django.db.models import F

from apps.core.managers import TenantManager, TenantQuerySet, UnscopedTenantManager
from apps.core.models import TenantModel
from apps.core.roles import INSTITUTE_WIDE_ROLES, Role, user_role

MIN_DURATION = 10
MAX_DURATION = 480  # 8 hours

# Links open in a new tab, so only web links (no ftp, no javascript).
meeting_url_validator = URLValidator(schemes=["http", "https"])

# A student or guardian sees a lecture only through an enrolment in the
# lecture's batch and one of its subjects. Both conditions sit in one
# filter() call, so they must hold on the same enrolment row.
_ENROLMENT = "subjects__student_links__"
STUDENT_LOOKUPS = {
    Role.STUDENT: f"{_ENROLMENT}student__user_id",
    Role.GUARDIAN: f"{_ENROLMENT}student__guardian_links__guardian__user_id",
}


class LectureStatus(models.TextChoices):
    SCHEDULED = "scheduled", "Scheduled"
    LIVE = "live", "Live"
    FINISHED = "finished", "Finished"
    CANCELLED = "cancelled", "Cancelled"


class DeliveryMode(models.TextChoices):
    MANUAL_LINK = "manual_link", "Manual link"
    IN_PERSON = "in_person", "In person"


class LectureQuerySet(TenantQuerySet):
    """Admins see the institute, a teacher their own lectures, a student or
    guardian the lectures of their (child's) batch and subjects."""

    def for_user(self, user: Any) -> LectureQuerySet:
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


class Lecture(TenantModel):
    title = models.CharField(max_length=200)
    teacher = models.ForeignKey(
        "people.TeacherProfile", on_delete=models.PROTECT, related_name="lectures"
    )
    batch = models.ForeignKey(
        "academics.Batch", on_delete=models.PROTECT, related_name="lectures"
    )
    subjects = models.ManyToManyField("academics.Subject", related_name="lectures")
    starts_at = models.DateTimeField()
    duration_minutes = models.PositiveSmallIntegerField(
        validators=[
            MinValueValidator(MIN_DURATION),
            MaxValueValidator(MAX_DURATION),
        ]
    )
    status = models.CharField(
        max_length=16, choices=LectureStatus.choices, default=LectureStatus.SCHEDULED
    )
    delivery_mode = models.CharField(
        max_length=16, choices=DeliveryMode.choices, default=DeliveryMode.MANUAL_LINK
    )
    meeting_url = models.URLField(
        max_length=500, blank=True, validators=[meeting_url_validator]
    )
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TenantManager.from_queryset(LectureQuerySet)()
    unscoped = UnscopedTenantManager.from_queryset(LectureQuerySet)()

    class Meta:
        ordering = ["starts_at", "pk"]
        indexes = [
            models.Index(fields=["institute", "starts_at"]),
            models.Index(fields=["teacher", "starts_at"]),
        ]

    def __str__(self) -> str:
        return self.title

    @property
    def ends_at(self) -> datetime:
        return self.starts_at + timedelta(minutes=self.duration_minutes)

    def clean(self) -> None:
        super().clean()
        for name in ("teacher", "batch"):
            related = getattr(self, name, None)
            if related is not None and related.institute_id != self.institute_id:
                raise ValidationError({name: "Must belong to the same institute."})
        if self.delivery_mode == DeliveryMode.MANUAL_LINK and not self.meeting_url:
            raise ValidationError(
                {"meeting_url": "Paste the meeting link for an online lecture."}
            )
        if self.delivery_mode == DeliveryMode.IN_PERSON and self.meeting_url:
            raise ValidationError(
                {"meeting_url": "An in-person lecture has no meeting link."}
            )

    def save(self, *args: Any, **kwargs: Any) -> None:
        # The fail-closed manager would hide rows from unique checks; there
        # are no unique constraints here, so skip them like the link models.
        self.full_clean(validate_unique=False, validate_constraints=False)
        super().save(*args, **kwargs)
