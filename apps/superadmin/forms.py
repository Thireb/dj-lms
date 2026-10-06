"""Super Admin institute forms."""

from __future__ import annotations

from crispy_forms.layout import Layout
from django import forms

from apps.institutes.models import Plan
from apps.ui.forms.base import BaseForm
from apps.ui.forms.layout import FormActions, Section


class CreateInstituteForm(BaseForm):
    save_label = "Create institute"

    def __init__(self, *args, cancel_url=None, **kwargs):
        self.cancel_url = cancel_url
        super().__init__(*args, **kwargs)

    name = forms.CharField(label="Institute name", max_length=255)
    plan = forms.ModelChoiceField(label="Plan", queryset=Plan.objects.order_by("code"))
    admin_email = forms.EmailField(label="Institute admin email")
    timezone = forms.CharField(
        label="Default time zone",
        max_length=63,
        initial="Asia/Karachi",
    )

    def get_layout(self):
        return Layout(
            Section(None, "name", "plan", "admin_email", "timezone"),
            FormActions(self.save_label, self.cancel_url),
        )


class EditInstituteForm(BaseForm):
    save_label = "Save institute"

    name = forms.CharField(label="Institute name", max_length=255)
    plan = forms.ModelChoiceField(label="Plan", queryset=Plan.objects.order_by("code"))
    is_active = forms.BooleanField(label="Active", required=False)

    def __init__(self, *args, cancel_url=None, is_active: bool = True, **kwargs):
        self.cancel_url = cancel_url
        super().__init__(*args, **kwargs)
        self.fields["is_active"].initial = is_active

    def get_layout(self):
        return Layout(
            Section(None, "name", "plan", "is_active"),
            FormActions(self.save_label, self.cancel_url),
        )
