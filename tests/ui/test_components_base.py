from apps.ui.components.base import Component


class _SmokeComponent(Component):
    template_name = "ui/components/badge.html"

    def __init__(self, text):
        super().__init__(text=text, tone="neutral")


def test_component_render_returns_html() -> None:
    html = _SmokeComponent("Hello").render()
    assert "Hello" in html
    assert "badge" in html
