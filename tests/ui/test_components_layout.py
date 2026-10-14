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


def test_grid_variants() -> None:
    from apps.ui.components.layout import Grid

    stats = str(Grid(["a", "b"], variant="stats"))
    unknown = str(Grid(["a"], variant="nope"))

    assert 'class="grid gap-3 sm:gap-4 grid-cols-2 lg:grid-cols-4"' in stats
    assert 'class="grid gap-5"' in unknown


def test_live_region_reloads_itself() -> None:
    import pytest
    from apps.ui.components.layout import LiveRegion

    html = str(LiveRegion("lecture-monitor", "<b>x</b>", url="/admin/x/"))
    unsafe = str(LiveRegion("panel", "x", url="javascript:alert(1)"))

    assert 'hx-get="/admin/x/" hx-trigger="every 30s"' in html
    assert 'hx-select="#lecture-monitor"' in html
    assert "<b>x" not in html  # text bodies are escaped
    assert "hx-get" not in unsafe and "javascript:" not in unsafe
    with pytest.raises(ValueError):
        LiveRegion('x" onclick="alert(1)', "x", url="/a/")


def test_sidebar_group_headings_have_enough_contrast() -> None:
    """External audit L2: axe flagged text-white/55 on the indigo sidebar."""
    from pathlib import Path

    template = Path("apps/ui/templates/ui/components/sidebar.html").read_text()

    assert "text-white/55" not in template
    assert 'text-white/70">{{ group.label }}' in template


def test_sidebar_background_grows_with_its_items() -> None:
    """Audit P4-4: with ``h-full`` the gradient stopped at the screen
    height, so the items below it (Account, Sign out) were white text on
    the light page. The aside grows with its items; its parent scrolls."""
    html = str(Sidebar(portal="teacher", groups=stub_menu_groups()))
    aside = html.split("<aside", 1)[1].split(">", 1)[0]
    classes = aside.split('class="', 1)[1].split('"', 1)[0].split()

    assert "min-h-full" in classes
    assert "h-full" not in classes
