from __future__ import annotations

from typing import Any

from django.urls import NoReverseMatch, reverse

from apps.core.roles import Role
from apps.ui.menu_items import MenuGroup, ResolvedMenuGroup, ResolvedMenuItem
from apps.ui.menus.admin import AdminMenu
from apps.ui.menus.guardian import GuardianMenu
from apps.ui.menus.student import StudentMenu
from apps.ui.menus.teacher import TeacherMenu

_PORTAL_MENUS = {
    "admin": AdminMenu,
    "teacher": TeacherMenu,
    "student": StudentMenu,
    "guardian": GuardianMenu,
}

_ROLE_PORTAL = {
    Role.INSTITUTE_ADMIN: "admin",
    Role.SUB_ADMIN: "admin",
    Role.TEACHER: "teacher",
    Role.STUDENT: "student",
    Role.GUARDIAN: "guardian",
}


def get_menu_class(portal: str):
    return _PORTAL_MENUS[portal]


def safe_reverse(url_name: str) -> str | None:
    try:
        return reverse(url_name)
    except NoReverseMatch:
        return None


def _institute_features(institute: Any | None) -> set[str]:
    if institute is None:
        return set()
    features = getattr(institute, "features", None)
    if features is None:
        return set()
    return set(features)


def resolve_menu_groups(
    groups: tuple[MenuGroup, ...] | list[MenuGroup],
    *,
    user: Any,
    institute: Any | None,
) -> list[ResolvedMenuGroup]:
    role = getattr(user, "role", None)
    allowed_menus = set(getattr(user, "allowed_menus", None) or [])
    features = _institute_features(institute)
    resolved: list[ResolvedMenuGroup] = []

    for group in groups:
        if (
            role == Role.SUB_ADMIN
            and group.menu_key
            and group.menu_key not in allowed_menus
        ):
            continue
        items: list[ResolvedMenuItem] = []
        for item in group.items:
            if item.feature and item.feature not in features:
                continue
            url = safe_reverse(item.url_name)
            disabled = url is None
            items.append(
                ResolvedMenuItem(
                    label=item.label,
                    url="#" if disabled else url,
                    icon=item.icon,
                    menu_key=item.menu_key,
                    disabled=disabled,
                    url_name=item.url_name,
                )
            )
        if items:
            resolved.append(
                ResolvedMenuGroup(
                    label=group.label,
                    items=tuple(items),
                    menu_key=group.menu_key,
                )
            )
    return resolved


def build_menu_groups(
    portal: str, user: Any, institute: Any | None
) -> list[ResolvedMenuGroup]:
    menu_class = get_menu_class(portal)
    return resolve_menu_groups(menu_class.groups(), user=user, institute=institute)


def portal_for_user(user: Any) -> str | None:
    role = getattr(user, "role", None)
    return _ROLE_PORTAL.get(role)


def list_unbuilt_menu_items() -> list[tuple[str, str, str]]:
    """Return (portal, group label, item label) for items whose URL name is missing."""
    unbuilt: list[tuple[str, str, str]] = []
    for portal, menu_class in _PORTAL_MENUS.items():
        for group in menu_class.groups():
            for item in group.items:
                if safe_reverse(item.url_name) is None:
                    unbuilt.append((portal, group.label, item.label))
    return unbuilt
