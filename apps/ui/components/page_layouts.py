from __future__ import annotations

from apps.ui.components.base import (
    Component,
    render_child,
    render_component_template,
)


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

    def render(self, request=None):
        ctx = self.get_context()
        if request is not None:
            header = ctx.get("header")
            if header is not None and hasattr(header, "render"):
                ctx["header"] = header.render(request=request)
            for key in ("stat_cards", "quick_actions", "sections"):
                items = ctx.get(key) or []
                ctx[key] = [
                    item.render(request=request) if hasattr(item, "render") else item
                    for item in items
                ]
        return render_component_template(self, ctx, request=request)


class ListPageBody(Component):
    template_name = "ui/layouts/pages/list.html"

    def __init__(self, header, filters=None, table=None, pagination=None, **props):
        super().__init__(
            header=header,
            filters=filters,
            table=table,
            pagination=pagination,
            **props,
        )

    def render(self, request=None):
        ctx = self.get_context()
        for key in ("header", "filters", "table", "pagination"):
            ctx[key] = render_child(ctx.get(key), request)
        return render_component_template(self, ctx, request=request)


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

    def render(self, request=None):
        ctx = self.get_context()
        ctx["header"] = render_child(ctx["header"], request)
        for key in ("primary_cards", "sidebar_cards"):
            ctx[key] = [render_child(card, request) for card in ctx[key]]
        return render_component_template(self, ctx, request=request)


class FormPageBody(Component):
    template_name = "ui/layouts/pages/form.html"

    def __init__(self, header, form=None, **props):
        super().__init__(header=header, form=form, **props)

    def render(self, request=None):
        ctx = self.get_context()
        if request is not None:
            header = ctx.get("header")
            if header is not None and hasattr(header, "render"):
                ctx["header"] = header.render(request=request)
            form = ctx.get("form")
            if form is not None and hasattr(form, "render"):
                ctx["form"] = form.render(request=request)
        return render_component_template(self, ctx, request=request)
