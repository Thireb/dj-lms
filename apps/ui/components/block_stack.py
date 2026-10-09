from apps.ui.components.base import (
    Component,
    render_child,
    render_component_template,
)


class BlockStack(Component):
    """Vertical stack of rendered components or plain text blocks."""

    template_name = "ui/components/block_stack.html"

    def __init__(self, blocks=None, **props):
        super().__init__(blocks=blocks or [], **props)

    def render(self, request=None):
        ctx = self.get_context()
        ctx["items"] = [
            {
                "html": render_child(block, request),
                "is_component": isinstance(block, Component),
            }
            for block in ctx["blocks"]
        ]
        return render_component_template(self, ctx, request=request)


class ButtonRow(Component):
    """Actions side by side (wraps on narrow screens), right-aligned in tables."""

    template_name = "ui/components/button_row.html"

    def __init__(self, items=None, **props):
        super().__init__(items=items or [], **props)

    def render(self, request=None):
        ctx = self.get_context()
        ctx["items"] = [render_child(item, request) for item in ctx["items"]]
        return render_component_template(self, ctx, request=request)
