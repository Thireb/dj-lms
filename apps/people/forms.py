"""Teacher forms (SPEC 4.2)."""

from __future__ import annotations

from crispy_forms.layout import Layout
from django import forms

from apps.academics.forms import BatchSubjectField
from apps.academics.services import Selections
from apps.people.models import cnic_validator
from apps.ui.forms.base import BaseForm
from apps.ui.forms.layout import FormActions, Section
from apps.ui.forms.widgets import DatePicker, PasswordInput


class TeacherForm(BaseForm):
    """Edit form; the create form adds the password."""

    save_label = "Save changes"

    full_name = forms.CharField(label="Full name", max_length=300)
    phone = forms.CharField(label="Phone", max_length=32)
    email = forms.EmailField(label="Email (sign-in)")
    cnic = forms.CharField(
        label="CNIC",
        max_length=13,
        required=False,
        validators=[cnic_validator],
        help_text="13 digits, no dashes.",
    )
    address = forms.CharField(label="Address", required=False, widget=forms.Textarea)
    joining_date = forms.DateField(
        label="Joining date", required=False, widget=DatePicker()
    )

    def __init__(
        self,
        *args,
        user: object,
        cancel_url: str,
        current: Selections | None = None,
        **kwargs,
    ):
        self.cancel_url = cancel_url
        super().__init__(*args, **kwargs)
        self.fields["batch_subjects"] = BatchSubjectField(
            label="Batches and subjects", user=user, current=current
        )

    def personal_fields(self) -> list[str]:
        return ["full_name", "phone", "email", "cnic", "address", "joining_date"]

    def get_layout(self):
        return Layout(
            Section("Personal and sign-in", *self.personal_fields()),
            Section("Teaching", "batch_subjects"),
            FormActions(self.save_label, self.cancel_url),
        )

    def selections(self) -> Selections:
        field = self.fields["batch_subjects"]
        return field.selections(self.cleaned_data["batch_subjects"])


class TeacherCreateForm(TeacherForm):
    save_label = "Add teacher"

    password = forms.CharField(
        label="Password",
        widget=PasswordInput(attrs={"autocomplete": "new-password"}),
        strip=False,
    )

    def personal_fields(self) -> list[str]:
        return [*super().personal_fields(), "password"]
