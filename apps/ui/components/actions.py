from apps.ui.components.base import Component, render_component_template
from apps.ui.safe_url import safe_url


class Button(Component):
    """A link (with ``url``) or a plain button. ``disabled=True`` shows a
    state that cannot be clicked yet; ``title`` explains it. ``new_tab=True``
    opens the link in a new tab without an opener (meeting links).
    ``submit=True`` (no ``url``) submits the form it is in."""

    template_name = "ui/components/button.html"
    variant = "primary"

    def __init__(
        self,
        label,
        variant=None,
        url=None,
        icon="",
        disabled=False,
        title="",
        new_tab=False,
        submit=False,
        **props,
    ):
        super().__init__(
            label=label,
            variant=variant or self.variant,
            url=safe_url(url) if url is not None and not disabled else None,
            icon=icon,
            disabled=disabled,
            title=title,
            new_tab=new_tab,
            submit=submit,
            **props,
        )


class PostButton(Component):
    """A one-button POST form with CSRF (when rendered with ``request``).
    ``new_tab=True`` sends it to a new tab without an opener (Join)."""

    template_name = "ui/components/post_button.html"

    def __init__(self, label, url, variant="primary", icon="", new_tab=False, **props):
        super().__init__(
            label=label,
            url=safe_url(url),
            variant=variant,
            icon=icon,
            new_tab=new_tab,
            **props,
        )


class IconButton(Component):
    """Icon-only link or button; ``label`` becomes its aria-label and tooltip.

    ``new_tab=True`` opens the link in a new tab without an opener (meeting
    links to other sites).
    """

    template_name = "ui/components/icon_button.html"

    def __init__(self, icon, label, url=None, **props):
        super().__init__(
            icon=icon,
            label=label,
            url=safe_url(url) if url is not None else None,
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

    def __init__(
        self,
        message,
        confirm_label,
        url,
        trigger_label="",
        variant="danger",
        fields=None,
        dismiss_label="Cancel",
        **props,
    ):
        """``dismiss_label`` closes the dialog; change it when the action
        itself is a cancel ("Keep lecture" next to "Cancel lecture")."""
        super().__init__(
            message=message,
            confirm_label=confirm_label,
            url=safe_url(url),
            trigger_label=trigger_label,
            variant=variant,
            fields=list(fields or []),
            dismiss_label=dismiss_label,
            **props,
        )


class CopyField(Component):
    """Read-only value with a copy button (for one-time links)."""

    template_name = "ui/components/copy_field.html"

    def __init__(self, label, value, **props):
        super().__init__(label=label, value=value, **props)


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
