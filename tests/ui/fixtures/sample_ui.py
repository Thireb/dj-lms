from __future__ import annotations

from types import SimpleNamespace

from apps.ui.menu_items import MenuItem


def demo_user(**overrides):
    base = SimpleNamespace(
        role="teacher",
        display_name="Demo user",
        allowed_menus=["dashboard"],
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
    return [SimpleNamespace(label="Main", items=[item])]


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


def fake_institute():
    return SimpleNamespace(name="Demo institute", timezone="Asia/Karachi")
