"""Menu items declare features that exist in core.features."""

from __future__ import annotations

from apps.core import features
from apps.ui.menu_items import MenuItem
from apps.ui.menus.admin import AdminMenu


def _walk_items() -> list[MenuItem]:
    items: list[MenuItem] = []
    for group in AdminMenu.groups():
        items.extend(group.items)
    return items


def test_admin_menu_feature_keys_are_known() -> None:
    known = set(features.ALL_FEATURE_KEYS)
    unknown: list[str] = []
    for item in _walk_items():
        if item.feature and item.feature not in known:
            unknown.append(f"{item.label} feature={item.feature!r}")
    assert unknown == []
