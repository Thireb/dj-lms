"""Super Admin portal navigation (institute management lives in superadmin app)."""

from __future__ import annotations

from apps.ui.menu_items import MenuGroup


class SuperMenu:
    @staticmethod
    def groups() -> tuple[MenuGroup, ...]:
        from apps.ui.menu_items import MenuGroup, MenuItem

        return (
            MenuGroup(
                label="Platform",
                items=(
                    MenuItem("Institutes", "super:institute_list", "building-2"),
                    MenuItem("Create institute", "super:institute_create", "plus"),
                ),
            ),
            MenuGroup(
                label="Account",
                items=(
                    MenuItem("My profile", "accounts:profile", "user"),
                    MenuItem("Sign out", "accounts:logout", "log-out"),
                ),
            ),
        )
