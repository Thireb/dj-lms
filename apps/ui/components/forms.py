from apps.ui.components.base import Component


class CrispyForm(Component):
    """Render a django-crispy-forms form via the ui/forms template pack."""

    template_name = "ui/components/crispy_form.html"

    def __init__(self, form, **props):
        super().__init__(form=form, **props)
