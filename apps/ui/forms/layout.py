from crispy_forms.layout import LayoutObject
from crispy_forms.utils import render_field
from django.template.loader import render_to_string


class Section(LayoutObject):
    template = "ui/forms/layout/section.html"

    def __init__(self, legend, *fields, css_class=None):
        self.legend = legend
        self.fields = list(fields)
        self.css_class = css_class or ""

    def render(self, form, context, template_pack=None, **kwargs):
        field_parts = [
            render_field(field, form, context, template_pack=template_pack)
            for field in self.fields
        ]
        return render_to_string(
            self.template,
            {
                "legend": self.legend,
                "field_parts": field_parts,
                "css_class": self.css_class,
            },
        )


class Row(LayoutObject):
    template = "ui/forms/layout/row.html"

    def __init__(self, *fields, css_class=None):
        self.fields = list(fields)
        self.css_class = css_class or ""

    def render(self, form, context, template_pack=None, **kwargs):
        field_parts = [
            render_field(field, form, context, template_pack=template_pack)
            for field in self.fields
        ]
        return render_to_string(
            self.template,
            {
                "field_parts": field_parts,
                "css_class": self.css_class,
            },
        )


class FormActions(LayoutObject):
    template = "ui/forms/layout/form_actions.html"

    def __init__(
        self,
        save_label="Save changes",
        cancel_url=None,
        cancel_label="Cancel",
        css_class=None,
        stacked=False,
    ):
        from apps.ui.safe_url import safe_url

        self.save_label = save_label
        self.cancel_url = safe_url(cancel_url) if cancel_url is not None else None
        self.cancel_label = cancel_label
        self.css_class = css_class or ""
        self.stacked = stacked

    def render(self, form, context, template_pack=None, **kwargs):
        return render_to_string(
            self.template,
            {
                "save_label": self.save_label,
                "cancel_url": self.cancel_url,
                "cancel_label": self.cancel_label,
                "css_class": self.css_class,
                "stacked": self.stacked,
            },
        )
