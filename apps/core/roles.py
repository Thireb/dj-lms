"""Product role constants and helpers (single source of truth)."""

from __future__ import annotations

from typing import Any


class Role:
    SUPER_ADMIN = "super_admin"
    INSTITUTE_ADMIN = "institute_admin"
    SUB_ADMIN = "sub_admin"
    TEACHER = "teacher"
    STUDENT = "student"
    GUARDIAN = "guardian"


# Roles whose for_user scope is the whole institute (ARCHITECTURE.md section 4).
INSTITUTE_WIDE_ROLES = frozenset(
    {Role.SUPER_ADMIN, Role.INSTITUTE_ADMIN, Role.SUB_ADMIN}
)


def user_role(user: Any) -> str | None:
    role = getattr(user, "role", None)
    if role is not None:
        return str(role)
    return None


def user_is_super_admin(user: Any) -> bool:
    if getattr(user, "is_super_admin", False):
        return True
    return user_role(user) == Role.SUPER_ADMIN


def user_institute_id(user: Any) -> int | None:
    institute_id = getattr(user, "institute_id", None)
    if institute_id is not None:
        return int(institute_id)
    institute = getattr(user, "institute", None)
    if institute is not None:
        return int(institute.pk)
    return None
