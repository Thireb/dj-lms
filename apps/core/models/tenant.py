"""Abstract base for institute-owned models."""

from django.db import models

from apps.core.managers import TenantManager


class TenantModel(models.Model):
    institute = models.ForeignKey(
        "institutes.Institute",
        on_delete=models.CASCADE,
        related_name="%(app_label)s_%(class)s_set",
    )

    objects = TenantManager()

    class Meta:
        abstract = True
