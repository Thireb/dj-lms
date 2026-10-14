from apps.ui.components.nav import (
    ChildSwitcher,
    FilterBar,
    NotificationBell,
    Pagination,
)
from django.core.paginator import Paginator
from tests.ui.fixtures.sample_ui import demo_user


def test_notification_bell_renders() -> None:
    html = str(NotificationBell(demo_user(), unread_count=2))
    assert "notification-bell" in html


def test_filter_bar_renders() -> None:
    from types import SimpleNamespace

    html = str(
        FilterBar(filters=[SimpleNamespace(name="q", label="Search", placeholder="")])
    )
    assert "filter-bar" in html


def test_pagination_renders() -> None:
    page_obj = Paginator(list(range(30)), 10).get_page(2)
    html = str(Pagination(page_obj))
    assert "pagination" in html
    assert "Page 2" in html


def test_filter_bar_keeps_value() -> None:
    from types import SimpleNamespace

    html = str(
        FilterBar(
            filters=[SimpleNamespace(name="q", label="Search", value="north")],
        )
    )
    assert 'value="north"' in html


def test_pagination_keeps_query() -> None:
    page_obj = Paginator(list(range(30)), 10).get_page(2)
    html = str(Pagination(page_obj, query="q=north"))
    assert "?q=north&page=3" in html
    assert "?q=north&page=1" in html


def test_child_switcher_marks_the_chosen_child_and_escapes() -> None:
    html = str(
        ChildSwitcher(
            [(3, "Sara <b>"), (7, "Omar")],
            chosen=7,
            url="/guardian/child/",
            next_url='/guardian/attendance/?x="1"',
        )
    )

    assert '<option value="7" selected>Omar</option>' in html
    assert '<option value="3">Sara &lt;b&gt;</option>' in html
    assert 'action="/guardian/child/"' in html
    assert 'value="/guardian/attendance/?x=&quot;1&quot;"' in html
    assert "<noscript>" in html


def test_child_switcher_drops_an_unsafe_url() -> None:
    html = str(ChildSwitcher([(1, "A")], chosen=1, url="javascript:x", next_url=""))
    assert "javascript:" not in html
