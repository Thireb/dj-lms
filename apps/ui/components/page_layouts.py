from __future__ import annotations

from apps.ui.components.base import Component


class DashboardPageBody(Component):
    template_name = "ui/layouts/pages/dashboard.html"

    def __init__(
        self,
        header,
        stat_cards=None,
        quick_actions=None,
        sections=None,
        **props,
    ):
        super().__init__(
            header=header,
            stat_cards=stat_cards or [],
            quick_actions=quick_actions or [],
            sections=sections or [],
            **props,
        )


class ListPageBody(Component):
    template_name = "ui/layouts/pages/list.html"

    def __init__(self, header, filters=None, table=None, **props):
        super().__init__(header=header, filters=filters, table=table, **props)


class DetailPageBody(Component):
    template_name = "ui/layouts/pages/detail.html"

    def __init__(
        self,
        header,
        primary_cards=None,
        sidebar_cards=None,
        **props,
    ):
        super().__init__(
            header=header,
            primary_cards=primary_cards or [],
            sidebar_cards=sidebar_cards or [],
            **props,
        )


class FormPageBody(Component):
    template_name = "ui/layouts/pages/form.html"

    def __init__(self, header, form=None, **props):
        super().__init__(header=header, form=form, **props)
