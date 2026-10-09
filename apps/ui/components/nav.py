from apps.ui.components.base import Component


class NotificationBell(Component):
    template_name = "ui/components/notification_bell.html"

    def __init__(self, user, unread_count=0, **props):
        super().__init__(user=user, unread_count=unread_count, **props)


def _value(field) -> str:
    """A filter may be a dict or an object; both carry an optional value."""
    if isinstance(field, dict):
        return field.get("value", "")
    return getattr(field, "value", "")


class FilterBar(Component):
    template_name = "ui/components/filter_bar.html"

    def __init__(self, filters=None, **props):
        super().__init__(filters=filters or [], **props)

    def get_context(self):
        ctx = super().get_context()
        ctx["active"] = any(_value(f) for f in ctx["filters"])
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
