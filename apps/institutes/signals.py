"""Institute lifecycle hooks."""

from __future__ import annotations

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.institutes.models import Institute, InstituteSettings


@receiver(post_save, sender=Institute)
def ensure_institute_settings(
    sender: type[Institute],
    instance: Institute,
    created: bool,
    **kwargs: object,
) -> None:
    if not created:
        return
    # unscoped: signal runs during institute create before tenant context exists.
    InstituteSettings.unscoped.get_or_create(institute=instance)
