from apps.ui.components.base import Component, render_component_template
from apps.ui.safe_url import safe_url


class Button(Component):
    template_name = "ui/components/button.html"
    variant = "primary"

    def __init__(self, label, variant=None, url=None, icon="", **props):
        super().__init__(
            label=label,
            variant=variant or self.variant,
            url=safe_url(url) if url is not None else None,
            icon=icon,
            **props,
        )


class QuickAction(Component):
    template_name = "ui/components/quick_action.html"

    def __init__(self, label, icon, url, **props):
        super().__init__(
            label=label,
            icon=icon,
            url=safe_url(url),
            **props,
        )


class ConfirmDialog(Component):
    template_name = "ui/components/confirm_dialog.html"

    def __init__(self, message, confirm_label, url, **props):
        super().__init__(
            message=message,
            confirm_label=confirm_label,
            url=safe_url(url),
            **props,
        )


class Toast(Component):
    template_name = "ui/components/toast.html"
    tone = "success"

    def __init__(self, message, tone=None, **props):
        super().__init__(message=message, tone=tone or self.tone, **props)


class SignOutForm(Component):
    """POST sign out with CSRF (Django 5 logout is POST-only)."""

    template_name = "ui/components/sign_out_form.html"

    def __init__(self, logout_url, **props):
        super().__init__(logout_url=safe_url(logout_url), **props)

    def render(self, request=None):
        return render_component_template(self, self.get_context(), request=request)
