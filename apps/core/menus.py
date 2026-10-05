"""Admin portal menu keys (single source of truth)."""

from __future__ import annotations

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
