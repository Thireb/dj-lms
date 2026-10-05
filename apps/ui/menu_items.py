from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MenuItem:
    label: str
    url_name: str
    icon: str
    menu_key: str | None = None
    feature: str | None = None


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


@dataclass(frozen=True)
class ResolvedMenuGroup:
    label: str
    items: tuple[ResolvedMenuItem, ...]
    menu_key: str | None = None
