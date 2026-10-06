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
                    MenuItem("Institutes", "super:institute_list", "building"),
                    MenuItem("Create institute", "super:institute_create", "plus"),
                ),
            ),
        )
