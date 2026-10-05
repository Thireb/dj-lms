from apps.ui.components.base import Component


class Button(Component):
    template_name = "ui/components/button.html"
    variant = "primary"

    def __init__(self, label, variant=None, url=None, icon="", **props):
        super().__init__(
            label=label,
            variant=variant or self.variant,
            url=url,
            icon=icon,
            **props,
        )


class QuickAction(Component):
    template_name = "ui/components/quick_action.html"

    def __init__(self, label, icon, url, **props):
        super().__init__(label=label, icon=icon, url=url, **props)


class ConfirmDialog(Component):
    template_name = "ui/components/confirm_dialog.html"

    def __init__(self, message, confirm_label, url, **props):
        super().__init__(
            message=message,
            confirm_label=confirm_label,
            url=url,
            **props,
        )


class Toast(Component):
    template_name = "ui/components/toast.html"
    tone = "success"

    def __init__(self, message, tone=None, **props):
        super().__init__(message=message, tone=tone or self.tone, **props)
