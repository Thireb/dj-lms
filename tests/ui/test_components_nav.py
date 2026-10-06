from apps.ui.components.nav import FilterBar, NotificationBell, Pagination
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
