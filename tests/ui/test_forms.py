from decimal import Decimal

from apps.core.tenancy import tenant_context
from apps.institutes.models import Institute
from apps.ui.forms.base import BaseForm, HtmxModalForm, TenantModelForm
from apps.ui.forms.layout import FormActions, Row, Section
from apps.ui.forms.widgets import DatePicker, MoneyInput, TimePicker
from crispy_forms.layout import Layout
from django import forms
from django.template import Context, Template
from tests.testapp.models import TenantProbe


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


class TenantProbeForm(TenantModelForm):
    class Meta:
        model = TenantProbe
        fields = ["label", "related"]


class TenantProbeWithInstituteFieldForm(TenantModelForm):
    class Meta:
        model = TenantProbe
        fields = ["label", "institute"]


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


def test_tenant_model_form_save_sets_institute(db, institute_a) -> None:
    with tenant_context(institute_a):
        form = TenantProbeForm(
            data={"label": "child"},
            institute=institute_a,
        )
        assert form.is_valid(), form.errors
        probe = form.save()
        assert probe.institute_id == institute_a.pk


def test_tenant_model_form_related_choices_scoped_to_institute(
    db,
    institute_a,
    institute_b,
    probe_a,
    probe_b,
) -> None:
    with tenant_context(institute_a):
        form = TenantProbeForm(institute=institute_a)
        related_pks = list(form.fields["related"].queryset.values_list("pk", flat=True))
        assert probe_a.pk in related_pks
        assert probe_b.pk not in related_pks


def test_tenant_model_form_rejects_cross_institute_related(
    db,
    institute_a,
    probe_b,
) -> None:
    with tenant_context(institute_a):
        form = TenantProbeForm(
            data={"label": "bad-link", "related": probe_b.pk},
            institute=institute_a,
        )
        assert not form.is_valid()
        assert "related" in form.errors


def test_tenant_model_form_strips_institute_field(db, institute_a, institute_b) -> None:
    form = TenantProbeWithInstituteFieldForm(institute=institute_a)
    assert "institute" not in form.fields


def test_tenant_model_form_cannot_move_record_to_other_institute_via_post(
    db,
    institute_a,
    institute_b,
    probe_a,
) -> None:
    with tenant_context(institute_a):
        form = TenantProbeWithInstituteFieldForm(
            data={"label": "moved", "institute": institute_b.pk},
            instance=probe_a,
            institute=institute_a,
        )
        assert form.is_valid(), form.errors
        saved = form.save()
        assert saved.institute_id == institute_a.pk


def test_tenant_model_form_rejects_cross_institute_edit(
    db,
    institute_a,
    probe_b,
) -> None:
    form = TenantProbeForm(
        data={"label": probe_b.label},
        instance=probe_b,
        institute=institute_a,
    )
    assert not form.is_valid()
    assert form.non_field_errors()


def test_widgets_render_expected_types() -> None:
    date_html = DatePicker().render("d", None, {"id": "id_d"})
    assert 'type="date"' in date_html
    time_html = TimePicker().render("t", None, {"id": "id_t"})
    assert 'type="time"' in time_html
    money_html = MoneyInput().render("amount", Decimal("10.00"), {"id": "id_amount"})
    assert 'type="number"' in money_html
