from urllib.parse import urlencode

from apps.ui.components.base import Component


class NotificationBell(Component):
    template_name = "ui/components/notification_bell.html"

    def __init__(self, user, unread_count=0, **props):
        super().__init__(user=user, unread_count=unread_count, **props)


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
