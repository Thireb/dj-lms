"""Tenant-aware queryset and manager."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.db import models

from apps.core.roles import user_institute_id, user_is_super_admin
from apps.core.tenancy import get_current_institute

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractBaseUser


class TenantQuerySet(models.QuerySet):
    def for_user(self, user: AbstractBaseUser | Any) -> TenantQuerySet:
        if user is None or not getattr(user, "is_authenticated", False):
            return self.none()
        if user_is_super_admin(user):
            return self.all()
        institute_id = user_institute_id(user)
        if institute_id is None:
            return self.none()
        return self.filter(institute_id=institute_id)

    def _apply_tenant_context(self) -> TenantQuerySet:
        institute = get_current_institute()
        if institute is not None:
            return self.filter(institute_id=institute.pk)
        return self.none()


class TenantManager(models.Manager.from_queryset(TenantQuerySet)):  # type: ignore[misc]
    def get_queryset(self) -> TenantQuerySet:
        return super().get_queryset()._apply_tenant_context()

    def for_user(self, user: AbstractBaseUser | Any) -> TenantQuerySet:
        return self.model.unscoped.get_queryset().for_user(user)


class UnscopedTenantManager(models.Manager.from_queryset(TenantQuerySet)):  # type: ignore[misc]
    def get_queryset(self) -> TenantQuerySet:
        return super().get_queryset()
