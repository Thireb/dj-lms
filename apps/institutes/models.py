from django.db import models


class Institute(models.Model):
    name = models.CharField(max_length=255)
    timezone = models.CharField(max_length=63, default="Asia/Karachi")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name
