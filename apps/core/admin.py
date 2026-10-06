"""Django admin helpers for tenant models."""

from __future__ import annotations

from django.contrib import admin


class TenantAdmin(admin.ModelAdmin):
    """ModelAdmin for :class:`~apps.core.models.TenantModel` subclasses.

    Uses ``unscoped`` because the default tenant manager is fail-closed (no
    current institute in admin), which would show an empty changelist.
    """

    def get_queryset(self, request):  # noqa: ANN001
        # unscoped: admin has no tenant context (AGENTS.md §6).
        qs = self.model.unscoped.get_queryset()
        ordering = self.get_ordering(request)
        if ordering:
            qs = qs.order_by(*ordering)
        return qs
