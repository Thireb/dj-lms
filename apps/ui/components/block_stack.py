from apps.ui.components.base import Component


class BlockStack(Component):
    """Vertical stack of rendered components or plain text blocks."""

    template_name = "ui/components/block_stack.html"

    def __init__(self, blocks=None, **props):
        super().__init__(blocks=blocks or [], **props)
