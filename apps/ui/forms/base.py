from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout
from django import forms

from apps.ui.forms.layout import FormActions, Row, Section

__all__ = [
    "BaseForm",
    "TenantModelForm",
    "HtmxModalForm",
    "Section",
    "Row",
    "FormActions",
]


class BaseForm(forms.Form):
    form_method = "post"
    save_label = "Save changes"
    cancel_url = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.form_tag = False
        self.helper.layout = self.get_layout()

    def get_layout(self):
        return Layout(
            *self.fields.keys(),
            FormActions(self.save_label, self.cancel_url),
        )


class TenantModelForm(BaseForm, forms.ModelForm):
    def __init__(self, *args, institute, **kwargs):
        self.institute = institute
        super().__init__(*args, **kwargs)


class HtmxModalForm(BaseForm):
    """Short form variant for modal dialogs (HTMX submit)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper.form_class = "htmx-modal-form"
