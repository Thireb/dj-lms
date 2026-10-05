from apps.ui.components.base import Component


class NotificationBell(Component):
    template_name = "ui/components/notification_bell.html"

    def __init__(self, user, unread_count=0, **props):
        super().__init__(user=user, unread_count=unread_count, **props)


class FilterBar(Component):
    template_name = "ui/components/filter_bar.html"

    def __init__(self, filters=None, **props):
        super().__init__(filters=filters or [], **props)


class Pagination(Component):
    template_name = "ui/components/pagination.html"

    def __init__(self, page_obj, **props):
        super().__init__(page_obj=page_obj, **props)
