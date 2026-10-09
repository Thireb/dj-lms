"""Lucide icon from the self-hosted sprite (one icon set, UI-GUIDELINES)."""

from __future__ import annotations

from django.templatetags.static import static

from apps.ui.components.base import Component
from apps.ui.icons import ICON_NAMES, ICON_SPRITE


class Icon(Component):
    """``<svg><use href="…/icons.svg#name">``. Unknown names render nothing.

    Icons are decorative (aria-hidden); the text next to them, or the
    button's aria-label, carries the meaning.
    """

    template_name = "ui/components/icon.html"

    def __init__(self, name: str, css_class: str = "", **props):
        super().__init__(name=name, css_class=css_class, **props)

    def get_context(self) -> dict:
        ctx = super().get_context()
        name = self.props["name"]
        ctx["href"] = f"{static(ICON_SPRITE)}#{name}" if name in ICON_NAMES else ""
        return ctx
