from apps.core.models import TenantModel
from django.db import models


class TenantProbe(TenantModel):
    label = models.CharField(max_length=64)

    class Meta:
        ordering = ["label"]

    def __str__(self) -> str:
        return self.label
