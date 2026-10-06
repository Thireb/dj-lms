"""Admin top-bar profile menu (roadmap 1.2 / BACKLOG C11)."""

from __future__ import annotations

from apps.ui.menu_items import MenuItem

ADMIN_PROFILE_ITEMS: tuple[MenuItem, ...] = (
    MenuItem("Account settings", "admin:account_settings", "user-gear"),
    MenuItem("Toolbar settings", "admin:toolbar_settings", "sliders"),
    MenuItem("Default portal", "admin:default_portal", "door-open"),
    MenuItem(
        "Institute settings",
        "admin:institute_settings",
        "building",
        admin_only=True,
    ),
    MenuItem(
        "Manage users",
        "admin:manage_users",
        "users-gear",
        admin_only=True,
    ),
    MenuItem(
        "Manage permissions",
        "admin:manage_permissions",
        "key",
        admin_only=True,
    ),
    MenuItem(
        "Select currency",
        "admin:select_currency",
        "coins",
        admin_only=True,
    ),
    MenuItem("Appearance", "admin:appearance", "palette"),
    MenuItem(
        "Sign out",
        "accounts:logout",
        "right-from-bracket",
        post_only=True,
    ),
)
