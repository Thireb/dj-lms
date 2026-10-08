"""Admin portal menu keys (single source of truth)."""

from __future__ import annotations

from apps.core.roles import Role, user_role

# Grantable top-level admin menu groups (sub-admin access).
DASHBOARDS = "dashboards"
INSTITUTE = "institute"
PEOPLE = "people"
ONLINE_LECTURES = "online_lectures"
FINANCE = "finance"
TEACHER_SALARY = "teacher_salary"
ACADEMIC = "academic"
MESSAGES = "messages"

ADMIN_MENU_KEYS: tuple[str, ...] = (
    DASHBOARDS,
    INSTITUTE,
    PEOPLE,
    ONLINE_LECTURES,
    FINANCE,
    TEACHER_SALARY,
    ACADEMIC,
    MESSAGES,
)


def user_has_menu(user: object, key: str) -> bool:
    """Whether to show links into an admin menu group (views still check access).

    Same rule as ``MenuRequiredMixin``: an institute admin has every key, a
    sub-admin only the keys in ``allowed_menus``.
    """
    role = user_role(user)
    if role == Role.INSTITUTE_ADMIN:
        return True
    if role == Role.SUB_ADMIN:
        return key in (getattr(user, "allowed_menus", None) or [])
    return False
