from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout
from django import forms
from django.core.exceptions import ValidationError

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


# Same look as DatePicker and PasswordInput; w-full keeps fields inside a
# 360px screen (a default textarea is about 412px wide).
INPUT_CLASSES = "field-control"  # 48px, soft fill, full width (input.css)
_STYLED_WIDGETS = (forms.widgets.Input, forms.Textarea, forms.Select)
_UNSTYLED_WIDGETS = (
    forms.CheckboxInput,
    forms.CheckboxSelectMultiple,
    forms.RadioSelect,
    forms.HiddenInput,
    forms.FileInput,
)


def style_widgets(form: forms.BaseForm) -> None:
    """Give text inputs, selects and textareas the shared classes."""
    for field in form.fields.values():
        widget = field.widget
        if not isinstance(widget, _STYLED_WIDGETS):
            continue
        if isinstance(widget, _UNSTYLED_WIDGETS) or widget.attrs.get("class"):
            continue
        widget.attrs["class"] = INPUT_CLASSES
        if isinstance(widget, forms.Textarea) and widget.attrs.get("rows") == "10":
            widget.attrs["rows"] = 3  # Django's default of 10 is too tall


class BaseForm(forms.Form):
    form_method = "post"
    save_label = "Save changes"
    cancel_url = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_widgets(self)
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
        self.fields.pop("institute", None)
        self._limit_tenant_related_fields()

    def _limit_tenant_related_fields(self) -> None:
        for field in self.fields.values():
            if not isinstance(field, forms.ModelChoiceField):
                continue
            model = field.queryset.model
            if issubclass(model, TenantModel):
                # unscoped: limit choices to this institute (not tenant context).
                field.queryset = model.unscoped.filter(institute=self.institute)

    def clean(self):
        cleaned_data = super().clean()
        if (
            self.instance.pk is not None
            and self.instance.institute_id != self.institute.pk
        ):
            raise ValidationError("This record belongs to another institute.")
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
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
