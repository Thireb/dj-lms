"""Super Admin institute forms."""

from __future__ import annotations

from zoneinfo import available_timezones

from crispy_forms.layout import Layout
from django import forms
from django.core.exceptions import ValidationError

from apps.accounts.models import User
from apps.institutes.constants import CURRENCY_CHOICES
from apps.institutes.models import Plan
from apps.ui.forms.base import BaseForm
from apps.ui.forms.layout import FormActions, Section


def _clean_timezone(value: str) -> str:
    value = (value or "").strip()
    if value not in available_timezones():
        raise ValidationError("Select a valid time zone.")
    return value


class InstituteFieldsForm(BaseForm):
    """Fields shared by create and edit."""

    name = forms.CharField(label="Institute name", max_length=255)
    plan = forms.ModelChoiceField(label="Plan", queryset=Plan.objects.order_by("code"))
    timezone = forms.CharField(
        label="Default time zone",
        max_length=63,
        initial="Asia/Karachi",
    )
    currency_code = forms.ChoiceField(
        label="Currency",
        choices=CURRENCY_CHOICES,
        initial="PKR",
    )

    def __init__(self, *args, cancel_url=None, **kwargs):
        self.cancel_url = cancel_url
        super().__init__(*args, **kwargs)

    def clean_timezone(self) -> str:
        return _clean_timezone(self.cleaned_data.get("timezone", ""))


class CreateInstituteForm(InstituteFieldsForm):
    save_label = "Create institute"

    admin_first_name = forms.CharField(label="Admin first name", max_length=150)
    admin_last_name = forms.CharField(
        label="Admin last name", max_length=150, required=False
    )
    admin_email = forms.EmailField(label="Admin email")

    def clean_admin_email(self) -> str:
        email = self.cleaned_data["admin_email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("A user with this email already exists.")
        return email

    def get_layout(self):
        return Layout(
            Section("Institute", "name", "plan", "timezone", "currency_code"),
            Section(
                "First admin", "admin_first_name", "admin_last_name", "admin_email"
            ),
            FormActions(self.save_label, self.cancel_url),
        )


class EditInstituteForm(InstituteFieldsForm):
    save_label = "Save institute"

    def get_layout(self):
        return Layout(
            Section(None, "name", "plan", "timezone", "currency_code"),
            FormActions(self.save_label, self.cancel_url),
        )
