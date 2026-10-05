from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout
from django import forms

from apps.core.models import TenantModel
from apps.core.tenancy import tenant_context
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
        self._limit_tenant_related_fields()

    def _limit_tenant_related_fields(self) -> None:
        for field in self.fields.values():
            if not isinstance(field, forms.ModelChoiceField):
                continue
            model = field.queryset.model
            if issubclass(model, TenantModel):
                field.queryset = model.unscoped.filter(institute=self.institute)

    def save(self, commit=True):
        instance = super().save(commit=False)
        if instance.pk is None and hasattr(instance, "institute_id"):
            instance.institute = self.institute
        if not commit:
            return instance
        with tenant_context(self.institute):
            instance.save()
            self.save_m2m()
        return instance


class HtmxModalForm(BaseForm):
    """Short form variant for modal dialogs (HTMX submit)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper.form_class = "htmx-modal-form"
