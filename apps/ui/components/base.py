from django.http import HttpRequest
from django.template.loader import render_to_string
from django.utils.safestring import SafeString, mark_safe


class Component:
    template_name: str = ""

    def __init__(self, **props):
        self.props = props

    def get_context(self) -> dict:
        return {"c": self, **self.props}

    def render(self, request: HttpRequest | None = None) -> SafeString:
        return mark_safe(
            render_to_string(self.template_name, self.get_context(), request=request)
        )

    def __html__(self) -> SafeString:
        return self.render()

    __str__ = __html__
