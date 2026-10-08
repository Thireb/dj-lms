from __future__ import annotations

import pytest
from apps.core.roles import Role
from apps.ui.components.layout import SidebarShell, TopNav
from apps.ui.menus.admin import AdminMenu
from apps.ui.menus.registry import build_menu_groups, list_unbuilt_menu_items
from tests.conftest import FakeUser
from tests.ui.fixtures.sample_ui import demo_user, fake_institute


def test_list_unbuilt_menu_items_includes_portal_urls() -> None:
    unbuilt = list_unbuilt_menu_items()
    assert unbuilt
    portals = {row[0] for row in unbuilt}
    assert "admin" in portals
    assert "teacher" in portals


def test_resolve_menu_items_use_hash_when_url_missing() -> None:
    groups = build_menu_groups(
        "admin",
        demo_user(role=Role.INSTITUTE_ADMIN),
        fake_institute(),
    )
    items = {item.url_name: item for group in groups for item in group.items}
    built = items["admin:dashboard_main"]
    unbuilt = items["admin:dashboard_salary"]  # Phase 8
    assert (built.url, built.disabled) == ("/admin/dashboard/", False)
    assert unbuilt.url == "#"
    assert unbuilt.disabled is True


def test_top_nav_renders_unbuilt_items_without_error() -> None:
    groups = build_menu_groups(
        "admin",
        demo_user(role=Role.INSTITUTE_ADMIN),
        fake_institute(),
    )
    html = str(TopNav(portal="admin", groups=groups))
    assert 'href="#"' in html
    assert "NoReverseMatch" not in html


def test_sub_admin_menu_filters_groups() -> None:
    user = demo_user(role=Role.SUB_ADMIN, allowed_menus=["people"])
    groups = build_menu_groups("admin", user, fake_institute())
    labels = [g.label for g in groups]
    assert "People" in labels
    assert "Finance" not in labels


def test_institute_feature_filter_hides_premium_items() -> None:
    user = demo_user(role=Role.INSTITUTE_ADMIN)
    institute = fake_institute(features=[])
    groups = build_menu_groups("admin", user, institute)
    finance_labels = [
        item.label
        for group in groups
        if group.label == "Finance"
        for item in group.items
    ]
    assert finance_labels == []


@pytest.mark.django_db
def test_all_portal_shells_render_with_real_menus(institute_a) -> None:
    from apps.core.features import PREMIUM_PLAN_FEATURES
    from apps.institutes.models import Plan
    from apps.ui.components.layout import TopNavShell

    premium = Plan.objects.get(code="premium")
    institute_a.plan = premium
    institute_a.save()
    assert PREMIUM_PLAN_FEATURES <= institute_a.features
    user = FakeUser(role=Role.INSTITUTE_ADMIN, institute=institute_a)
    admin_html = str(TopNavShell(portal="admin", user=user, institute=institute_a))
    assert "top-nav-shell" in admin_html

    teacher = FakeUser(role=Role.TEACHER, institute=institute_a)
    sidebar_html = str(
        SidebarShell(portal="teacher", user=teacher, institute=institute_a)
    )
    assert "sidebar" in sidebar_html


def test_admin_menu_groups_use_core_menu_keys() -> None:
    keys = {g.menu_key for g in AdminMenu.groups() if g.menu_key}
    assert "people" in keys
    assert "finance" in keys
