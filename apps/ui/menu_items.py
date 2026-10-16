from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MenuItem:
    label: str
    url_name: str
    icon: str
    menu_key: str | None = None
    feature: str | None = None
    post_only: bool = False
    admin_only: bool = False
    # A URL name that answers a small count badge (HTMX, every 60 seconds).
    badge: str | None = None


@dataclass(frozen=True)
class MenuGroup:
    label: str
    items: tuple[MenuItem, ...]
    menu_key: str | None = None


@dataclass(frozen=True)
class ResolvedMenuItem:
    label: str
    url: str
    icon: str
    menu_key: str | None
    disabled: bool
    url_name: str
    post_only: bool = False
    badge_url: str = ""


@dataclass(frozen=True)
class ResolvedMenuGroup:
    label: str
    items: tuple[ResolvedMenuItem, ...]
    menu_key: str | None = None
