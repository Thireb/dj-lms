from apps.core.models import TenantModel
from django.db import models


class TenantProbe(TenantModel):
    label = models.CharField(max_length=64)
    related = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="linked_probes",
    )

    class Meta:
        ordering = ["label"]

    def __str__(self) -> str:
        return self.label
