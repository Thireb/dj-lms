"""Admin profile menu hides admin_only items from sub_admin (C11)."""

from __future__ import annotations

from apps.core.roles import Role
from apps.ui.menus.registry import build_profile_menu_items
from tests.ui.fixtures.sample_ui import demo_user, fake_institute


def test_sub_admin_profile_menu_hides_admin_only_items() -> None:
    user = demo_user(role=Role.SUB_ADMIN)
    items = build_profile_menu_items(user, fake_institute())
    labels = [item.label for item in items]
    assert "Institute settings" not in labels
    assert "Manage users" not in labels
    assert "Sign out" in labels


def test_institute_admin_sees_institute_settings_link() -> None:
    user = demo_user(role=Role.INSTITUTE_ADMIN)
    items = build_profile_menu_items(user, fake_institute())
    labels = [item.label for item in items]
    assert "Institute settings" in labels
    settings = next(i for i in items if i.label == "Institute settings")
    assert settings.disabled is False
