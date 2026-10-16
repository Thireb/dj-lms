from urllib.parse import urlencode

from apps.ui.components.base import Component
from apps.ui.safe_url import safe_url


class ChildSwitcher(Component):
    """Guardian header: choose the child that every guardian page follows.
    A POST form (CSRF when rendered with ``request``); the select sends it
    on change, and a "Show" button does it without JavaScript. ``options``
    is a list of (value, label); ``next_url`` is where to go back."""

    template_name = "ui/components/child_switcher.html"

    def __init__(self, options, chosen, url, next_url, **props):
        super().__init__(
            options=[(str(value), label) for value, label in options],
            chosen=str(chosen),
            url=safe_url(url),
            next_url=next_url,
            **props,
        )


# Roles that get notifications (SPEC 7); the super admin has none.
BELL_ROLES = {"institute_admin", "sub_admin", "teacher", "student", "guardian"}
COUNT_CAP = 99  # the badge shows "99+" above this


class NotificationCount(Component):
    """The bell's unread count: a badge and words for screen readers. The
    bell loads it on each page and every 60 seconds (HTMX)."""

    template_name = "ui/components/notification_count.html"

    def __init__(self, unread_count=0, **props):
        count = max(0, int(unread_count))
        shown = f"{COUNT_CAP}+" if count > COUNT_CAP else str(count)
        super().__init__(unread_count=count, shown=shown, **props)


class NotificationBell(Component):
    """Top bar bell (roadmap 6.1). A link to the Notifications page; with
    JavaScript it opens the latest notifications (``panel_url``, loaded
    when opened) and keeps the unread count fresh (``count_url``)."""

    template_name = "ui/components/notification_bell.html"

    def __init__(self, user, unread_count=0, **props):
        super().__init__(user=user, unread_count=unread_count, **props)

    def get_context(self):
        from django.urls import reverse

        ctx = super().get_context()
        ctx["enabled"] = getattr(self.props["user"], "role", "") in BELL_ROLES
        ctx["count"] = NotificationCount(self.props["unread_count"])
        ctx["list_url"] = reverse("notifications:list")
        ctx["count_url"] = reverse("notifications:count")
        ctx["panel_url"] = reverse("notifications:panel")
        return ctx


class NotificationPanel(Component):
    """The bell's list: the latest notifications, each a POST button that
    marks it read and opens its link, then "Mark all as read" and "See all".
    ``rows`` have ``text``, ``when``, ``open_url`` and ``is_read``. Render
    with ``request`` for the CSRF tokens."""

    template_name = "ui/components/notification_panel.html"

    def __init__(self, rows, list_url, read_all_url, next_url="", **props):
        super().__init__(
            rows=[
                {
                    "text": row.text,
                    "when": row.when,
                    "open_url": safe_url(row.open_url),
                    "is_read": row.is_read,
                }
                for row in rows
            ],
            list_url=safe_url(list_url),
            read_all_url=safe_url(read_all_url),
            next_url=safe_url(next_url),
            **props,
        )


def _get(field, key: str, default=""):
    """A filter may be a dict or an object."""
    if isinstance(field, dict):
        return field.get(key, default)
    return getattr(field, key, default)


def _value(field) -> str:
    return _get(field, "value")


class FilterBar(Component):
    """Search fields and selects; a filter with ``hidden=True`` is a hidden
    input that keeps a value (such as the chosen tab) when filters apply.
    A select with ``kept=True`` (such as a guardian's chosen child) does not
    count for "Clear", and "Clear" keeps its value. ``input_type="date"``
    renders a date field."""

    template_name = "ui/components/filter_bar.html"

    def __init__(self, filters=None, **props):
        super().__init__(filters=filters or [], **props)

    def get_context(self):
        ctx = super().get_context()
        # A hidden field (for example the chosen tab) is kept on submit but
        # is not a filter the user can clear.
        ctx["active"] = any(
            _value(f)
            for f in ctx["filters"]
            if not _get(f, "hidden", False) and not _get(f, "kept", False)
        )
        ctx["clear_query"] = urlencode(
            [(_get(f, "name"), _value(f)) for f in ctx["filters"] if _get(f, "kept")]
        )
        return ctx


class Pagination(Component):
    template_name = "ui/components/pagination.html"

    def __init__(self, page_obj, query="", **props):
        super().__init__(page_obj=page_obj, query=query, **props)

    def get_context(self):
        ctx = super().get_context()
        page = self.props["page_obj"]
        paginator = page.paginator
        ctx["page_numbers"] = list(
            paginator.get_elided_page_range(page.number, on_each_side=1, on_ends=1)
        )
        ctx["ellipsis"] = paginator.ELLIPSIS
        return ctx


class MenuBadge(Component):
    """A menu item's count (unread messages), loaded with HTMX by the menu.
    Nothing shows for 0; "99+" above 99."""

    template_name = "ui/components/menu_badge.html"

    def __init__(self, count=0, **props):
        count = max(0, int(count))
        shown = f"{COUNT_CAP}+" if count > COUNT_CAP else str(count)
        super().__init__(count=count, shown=shown, **props)
