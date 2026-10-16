"""Messages (roadmap 6.3, FEATURES 11, SPEC 4.19 and 6.5).

A ``Thread`` has a subject and its ``Message`` rows. Each person in it has a
``ThreadMember`` row with their own state: read up to, starred, in the
trash, deleted forever (SPEC 2: read state is per user). A ``Draft`` is a
new message not sent yet. A ``Broadcast`` goes to many people as one
private thread each, so a reply reaches only the sender (owner decision
2026-10-16).
"""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.db import models

from apps.core.managers import TenantManager, TenantQuerySet, UnscopedTenantManager
from apps.core.models import TenantModel
from apps.core.roles import INSTITUTE_WIDE_ROLES, user_role

MAX_SUBJECT = 200
MAX_BODY = 5000


class ThreadQuerySet(TenantQuerySet):
    """Admins and sub-admins see every thread of the institute (the Message
    Monitor, FEATURES 11); everyone else only the threads they are in."""

    def for_user(self, user: Any) -> ThreadQuerySet:
        scoped = super().for_user(user)
        if user_role(user) in INSTITUTE_WIDE_ROLES:
            return scoped
        return scoped.filter(members__user_id=getattr(user, "pk", None)).distinct()


class OwnRowsQuerySet(TenantQuerySet):
    """Every role sees only their own rows, admins too."""

    owner_field = "user_id"

    def for_user(self, user: Any) -> OwnRowsQuerySet:
        scoped = super().for_user(user)
        return scoped.filter(**{self.owner_field: getattr(user, "pk", None)})


class DraftQuerySet(OwnRowsQuerySet):
    owner_field = "owner_id"


class MessageQuerySet(TenantQuerySet):
    """The messages of the threads the user may read."""

    def for_user(self, user: Any) -> MessageQuerySet:
        scoped = super().for_user(user)
        if user_role(user) in INSTITUTE_WIDE_ROLES:
            return scoped
        return scoped.filter(thread__members__user_id=getattr(user, "pk", None))


class BroadcastQuerySet(TenantQuerySet):
    """Only admins and sub-admins see broadcasts as such; each recipient
    sees their own thread."""

    def for_user(self, user: Any) -> BroadcastQuerySet:
        scoped = super().for_user(user)
        if user_role(user) in INSTITUTE_WIDE_ROLES:
            return scoped
        return scoped.none()


class Audience(models.TextChoices):
    ALL = "all", "Everyone"
    TEACHERS = "teachers", "Teachers"
    STUDENTS = "students", "Students"
    GUARDIANS = "guardians", "Guardians"
    BATCH = "batch", "A batch"


class Broadcast(TenantModel):
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="broadcasts"
    )
    audience = models.CharField(max_length=16, choices=Audience.choices)
    batch = models.ForeignKey(
        "academics.Batch",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="broadcasts",
    )
    subject = models.CharField(max_length=MAX_SUBJECT)
    body = models.TextField()
    recipients = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField()

    objects = TenantManager.from_queryset(BroadcastQuerySet)()
    unscoped = UnscopedTenantManager.from_queryset(BroadcastQuerySet)()

    class Meta:
        ordering = ["-created_at", "-pk"]

    def __str__(self) -> str:
        return self.subject


class Thread(TenantModel):
    subject = models.CharField(max_length=MAX_SUBJECT)
    broadcast = models.ForeignKey(
        Broadcast,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="threads",
    )
    created_at = models.DateTimeField()
    last_message_at = models.DateTimeField()

    objects = TenantManager.from_queryset(ThreadQuerySet)()
    unscoped = UnscopedTenantManager.from_queryset(ThreadQuerySet)()

    class Meta:
        ordering = ["-last_message_at", "-pk"]
        indexes = [models.Index(fields=["institute", "last_message_at"])]

    def __str__(self) -> str:
        return self.subject


class ThreadMember(TenantModel):
    thread = models.ForeignKey(Thread, on_delete=models.CASCADE, related_name="members")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="message_threads",
    )
    last_read_at = models.DateTimeField(null=True, blank=True)
    starred = models.BooleanField(default=False)
    trashed_at = models.DateTimeField(null=True, blank=True)
    deleted = models.BooleanField(default=False)  # "Delete forever" from Trash

    objects = TenantManager.from_queryset(OwnRowsQuerySet)()
    unscoped = UnscopedTenantManager.from_queryset(OwnRowsQuerySet)()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["thread", "user"], name="messaging_member_once"
            )
        ]

    def __str__(self) -> str:
        return f"{self.user} in {self.thread}"


class Message(TenantModel):
    thread = models.ForeignKey(
        Thread, on_delete=models.CASCADE, related_name="messages"
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_messages",
    )
    body = models.TextField()
    created_at = models.DateTimeField()

    objects = TenantManager.from_queryset(MessageQuerySet)()
    unscoped = UnscopedTenantManager.from_queryset(MessageQuerySet)()

    class Meta:
        ordering = ["created_at", "pk"]

    def __str__(self) -> str:
        return f"{self.sender}: {self.body[:40]}"


class Draft(TenantModel):
    """A new message the owner saved with "Save draft" (no autosave)."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="message_drafts",
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    subject = models.CharField(max_length=MAX_SUBJECT, blank=True)
    body = models.TextField(blank=True)
    updated_at = models.DateTimeField()

    objects = TenantManager.from_queryset(DraftQuerySet)()
    unscoped = UnscopedTenantManager.from_queryset(DraftQuerySet)()

    class Meta:
        ordering = ["-updated_at", "-pk"]

    def __str__(self) -> str:
        return self.subject or "(No subject)"
