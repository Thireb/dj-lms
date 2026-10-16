"""In-app notifications (roadmap 6.1, SPEC 7): one row per user and event.

Rows are made only by ``notifications.services.notify`` (ARCHITECTURE 10).
"""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.db import models

from apps.core.managers import TenantManager, TenantQuerySet, UnscopedTenantManager
from apps.core.models import TenantModel


class NotificationQuerySet(TenantQuerySet):
    """Every role sees only their own notifications, admins too."""

    def for_user(self, user: Any) -> NotificationQuerySet:
        scoped = super().for_user(user)
        return scoped.filter(user_id=getattr(user, "pk", None))


class Notification(TenantModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    event = models.CharField(max_length=40)
    text = models.CharField(max_length=300)
    link = models.CharField(max_length=300, blank=True, default="")
    created_at = models.DateTimeField()
    read_at = models.DateTimeField(null=True, blank=True)

    objects = TenantManager.from_queryset(NotificationQuerySet)()
    unscoped = UnscopedTenantManager.from_queryset(NotificationQuerySet)()

    class Meta:
        ordering = ["-created_at", "-pk"]
        indexes = [
            models.Index(fields=["user", "read_at"], name="notification_user_read"),
            models.Index(fields=["created_at"], name="notification_created"),
        ]

    def __str__(self) -> str:
        return self.text

    @property
    def is_read(self) -> bool:
        return self.read_at is not None
