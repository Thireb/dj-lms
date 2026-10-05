"""Tenant-aware queryset and manager."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.db import models

from apps.core.tenancy import get_current_institute

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractBaseUser


class Role:
    SUPER_ADMIN = "super_admin"
    INSTITUTE_ADMIN = "institute_admin"
    SUB_ADMIN = "sub_admin"
    TEACHER = "teacher"
    STUDENT = "student"
    GUARDIAN = "guardian"


def _user_role(user: Any) -> str | None:
    role = getattr(user, "role", None)
    if role is not None:
        return str(role)
    return None


def _is_super_admin(user: Any) -> bool:
    if getattr(user, "is_super_admin", False):
        return True
    return _user_role(user) == Role.SUPER_ADMIN


def _user_institute_id(user: Any) -> int | None:
    institute_id = getattr(user, "institute_id", None)
    if institute_id is not None:
        return int(institute_id)
    institute = getattr(user, "institute", None)
    if institute is not None:
        return int(institute.pk)
    return None


class TenantQuerySet(models.QuerySet):
    def for_user(self, user: AbstractBaseUser | Any) -> TenantQuerySet:
        if _is_super_admin(user):
            return self.all()
        institute_id = _user_institute_id(user)
        if institute_id is None:
            return self.none()
        return self.filter(institute_id=institute_id)

    def _apply_tenant_context(self) -> TenantQuerySet:
        institute = get_current_institute()
        if institute is not None:
            return self.filter(institute_id=institute.pk)
        return self


class TenantManager(models.Manager.from_queryset(TenantQuerySet)):  # type: ignore[misc]
    def get_queryset(self) -> TenantQuerySet:
        return super().get_queryset()._apply_tenant_context()
