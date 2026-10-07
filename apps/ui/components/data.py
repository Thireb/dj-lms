from __future__ import annotations

from collections.abc import Callable
from typing import Any

from apps.ui.components.base import (
    Component,
    render_child,
    render_component_template,
)
from apps.ui.progress_value import clamp_progress_value
from apps.ui.safe_url import safe_url


class Column:
    def __init__(
        self,
        key: str,
        label: str,
        render: Callable[[Any], Any] | None = None,
    ):
        self.key = key
        self.label = label
        self.render = render

    def cell(self, row: Any) -> Any:
        if self.render is not None:
            return self.render(row)
        if isinstance(row, dict):
            return row.get(self.key, "")
        return getattr(row, self.key, "")


class StatCard(Component):
    template_name = "ui/components/stat_card.html"
    tone = "neutral"

    def __init__(
        self,
        value,
        label,
        note="",
        icon="",
        tone=None,
        **props,
    ):
        super().__init__(
            value=value,
            label=label,
            note=note,
            icon=icon,
            tone=tone or self.tone,
            **props,
        )


class DataTable(Component):
    template_name = "ui/components/data_table.html"
    columns: list[Column] = []
    empty_title = "Nothing here yet."
    row_actions: list = []

    def __init__(self, rows, **props):
        super().__init__(rows=rows, **props)

    def get_context(self):
        ctx = super().get_context()
        columns = self.props.get("columns") or self.columns
        rows = self.props["rows"]
        ctx["columns"] = columns
        ctx["cells"] = [[col.cell(row) for col in columns] for row in rows]
        ctx["empty_title"] = self.props.get("empty_title", self.empty_title)
        ctx["row_actions"] = self.props.get("row_actions", self.row_actions)
        return ctx

    def render(self, request=None):
        ctx = self.get_context()
        ctx["cells"] = [
            [render_child(cell, request) for cell in row] for row in ctx["cells"]
        ]
        return render_component_template(self, ctx, request=request)


class Badge(Component):
    template_name = "ui/components/badge.html"
    tone = "neutral"

    def __init__(self, text, tone=None, **props):
        super().__init__(text=text, tone=tone or self.tone, **props)


class Avatar(Component):
    template_name = "ui/components/avatar.html"
    size = "md"

    def __init__(self, name, size=None, **props):
        super().__init__(name=name, size=size or self.size, **props)


class ProgressBar(Component):
    template_name = "ui/components/progress_bar.html"
    tone = "primary"

    def __init__(self, value, label="", tone=None, **props):
        super().__init__(
            value=clamp_progress_value(value),
            label=label,
            tone=tone or self.tone,
            **props,
        )


class ChartCard(Component):
    template_name = "ui/components/chart_card.html"

    def __init__(self, title, chart_id, data_url, **props):
        super().__init__(
            title=title,
            chart_id=chart_id,
            data_url=safe_url(data_url),
            **props,
        )


class EmptyState(Component):
    template_name = "ui/components/empty_state.html"

    def __init__(self, title, text="", action=None, **props):
        super().__init__(title=title, text=text, action=action, **props)
