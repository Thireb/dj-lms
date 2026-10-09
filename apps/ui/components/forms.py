from apps.ui.components.base import Component, render_component_template


class CrispyForm(Component):
    """Render a django-crispy-forms form via the ui/forms template pack."""

    template_name = "ui/components/crispy_form.html"

    def __init__(self, form, **props):
        super().__init__(form=form, **props)

    def render(self, request=None):
        return render_component_template(self, self.get_context(), request=request)


class PublicPostForm(Component):
    """Public page POST wrapper (CSRF + crispy body without nested form tag)."""

    template_name = "ui/components/public_post_form.html"

    def __init__(self, *, action: str, body, **props):
        super().__init__(action=action, body=body, **props)

    def render(self, request=None):
        ctx = self.get_context()
        body = ctx.get("body")
        if request is not None and body is not None and hasattr(body, "render"):
            ctx["body"] = body.render(request=request)
        return render_component_template(self, ctx, request=request)


class PortalPostForm(Component):
    """Portal FormPage POST wrapper (CSRF + multipart + crispy body)."""

    template_name = "ui/components/portal_post_form.html"

    def __init__(self, *, action: str, body, framed: bool = True, **props):
        super().__init__(action=action, body=body, framed=framed, **props)

    def render(self, request=None):
        ctx = self.get_context()
        body = ctx.get("body")
        if request is not None and body is not None and hasattr(body, "render"):
            ctx["body"] = body.render(request=request)
        return render_component_template(self, ctx, request=request)
