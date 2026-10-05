from apps.ui.components.actions import Button
from apps.ui.components.layout import (
    HeroBanner,
    Modal,
    PageHeader,
    SectionCard,
    Sidebar,
    SidebarShell,
    Tabs,
    TopNav,
    TopNavShell,
)
from tests.ui.fixtures.sample_ui import demo_user, stub_menu_groups


def test_top_nav_shell_renders() -> None:
    html = str(TopNavShell(portal="admin", user=demo_user(), groups=stub_menu_groups()))
    assert "top-nav-shell" in html
    assert "data-portal" in html


def test_sidebar_shell_renders() -> None:
    html = str(
        SidebarShell(portal="teacher", user=demo_user(), groups=stub_menu_groups())
    )
    assert "sidebar-shell" in html or "sidebar" in html


def test_top_nav_renders_group_label() -> None:
    html = str(TopNav(portal="admin", groups=stub_menu_groups()))
    assert "Main" in html
    assert "top-nav" in html


def test_sidebar_renders() -> None:
    html = str(Sidebar(portal="teacher", groups=stub_menu_groups()))
    assert "sidebar" in html


def test_hero_banner_renders() -> None:
    html = str(HeroBanner(title="Welcome", subtitle="Demo"))
    assert "Welcome" in html
    assert "hero-banner" in html


def test_page_header_renders() -> None:
    html = str(PageHeader(title="Students", breadcrumb=["Admin"]))
    assert "Students" in html
    assert "page-header" in html


def test_section_card_renders() -> None:
    html = str(SectionCard(title="Stats", body="Body text"))
    assert "Stats" in html
    assert "section-card" in html


def test_tabs_renders() -> None:
    from types import SimpleNamespace

    tabs = [SimpleNamespace(id="a", label="Tab A", url="#a")]
    html = str(Tabs(tabs=tabs, active="a"))
    assert "Tab A" in html
    assert "tabs" in html


def test_modal_renders() -> None:
    html = str(Modal(id="m1", title="Confirm", body=Button("OK")))
    assert "Confirm" in html
    assert "modal" in html
