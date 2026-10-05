from __future__ import annotations

from types import SimpleNamespace

from apps.ui.menu_items import MenuGroup, MenuItem
from apps.ui.menus.registry import resolve_menu_groups


def demo_user(**overrides):
    base = SimpleNamespace(
        role="teacher",
        display_name="Demo user",
        allowed_menus=["dashboards", "people"],
    )
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


def stub_menu_groups():
    item = MenuItem(
        label="Dashboard",
        url_name="dev_components",
        icon="gauge",
        menu_key="dashboard",
    )
    group = MenuGroup(label="Main", items=(item,))
    return resolve_menu_groups((group,), user=demo_user(), institute=None)


def fake_lectures():
    return [
        SimpleNamespace(
            title="Sample lecture",
            scheduled_at="2026-08-16T15:00:00+00:00",
            meeting_link="https://meet.example.invalid/x",
            status="scheduled",
            day="Mon 16 Aug 2026",
        )
    ]


def fake_institute(**overrides):
    base = SimpleNamespace(
        name="Demo institute",
        timezone="Asia/Karachi",
        features=["fees", "payroll", "messaging", "homework", "lesson_plans", "leave"],
    )
    for key, value in overrides.items():
        setattr(base, key, value)
    return base
