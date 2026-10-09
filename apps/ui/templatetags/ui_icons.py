"""``{% load ui_icons %}{% icon "bell" "h-5 w-5" %}`` for templates."""

from __future__ import annotations

from django import template
from django.utils.safestring import SafeString

from apps.ui.components.icon import Icon

register = template.Library()


@register.simple_tag
def icon(name: str, css_class: str = "") -> SafeString:
    return Icon(name or "", css_class=css_class).render()
