from __future__ import annotations

from apps.ui.components.base import Component


class ProfileMenu(Component):
    template_name = "ui/components/profile_menu.html"

    def __init__(self, items=None, **props):
        super().__init__(items=items or [], **props)
