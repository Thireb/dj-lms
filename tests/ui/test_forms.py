from decimal import Decimal

from apps.institutes.models import Institute
from apps.ui.forms.base import BaseForm, HtmxModalForm, TenantModelForm
from apps.ui.forms.layout import FormActions, Row, Section
from apps.ui.forms.widgets import DatePicker, MoneyInput, TimePicker
from crispy_forms.layout import Layout
from django import forms
from django.template import Context, Template


class SampleForm(BaseForm):
    name = forms.CharField()
    email = forms.EmailField()

    def get_layout(self):
        return Layout(
            Section("Contact", Row("name", "email")),
            FormActions(self.save_label, self.cancel_url),
        )


class SampleModalForm(HtmxModalForm):
    note = forms.CharField()


class InstituteForm(TenantModelForm):
    class Meta:
        model = Institute
        fields = ["name"]


def test_base_form_crispy_render() -> None:
    template = Template("{% load crispy_forms_tags %}{% crispy form %}")
    html = template.render(Context({"form": SampleForm()}))
    assert "Contact" in html
    assert "Save changes" in html


def test_htmx_modal_form_helper_class() -> None:
    form = SampleModalForm()
    assert form.helper.form_class == "htmx-modal-form"


def test_tenant_model_form_accepts_institute(db) -> None:
    institute = Institute.objects.create(name="Test institute")
    form = InstituteForm(institute=institute)
    assert form.institute == institute


def test_widgets_render_expected_types() -> None:
    date_html = DatePicker().render("d", None, {"id": "id_d"})
    assert 'type="date"' in date_html
    time_html = TimePicker().render("t", None, {"id": "id_t"})
    assert 'type="time"' in time_html
    money_html = MoneyInput().render("amount", Decimal("10.00"), {"id": "id_amount"})
    assert 'type="number"' in money_html
