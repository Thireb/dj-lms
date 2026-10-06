"""Authentication and password forms."""

from __future__ import annotations

from zoneinfo import available_timezones

from crispy_forms.layout import Layout
from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from apps.accounts.models import User
from apps.ui.forms.base import BaseForm
from apps.ui.forms.layout import FormActions, Section
from apps.ui.forms.widgets import PasswordInput


class LoginForm(BaseForm):
    save_label = "Sign in"

    email = forms.EmailField(label="Email")
    password = forms.CharField(label="Password", widget=PasswordInput())
    remember_me = forms.BooleanField(
        label="Remember me",
        required=False,
        initial=False,
    )

    def __init__(self, *args, cancel_url=None, next_url=None, **kwargs):
        self.cancel_url = cancel_url
        super().__init__(*args, **kwargs)
        if next_url:
            self.fields["next"] = forms.CharField(
                widget=forms.HiddenInput(),
                initial=next_url,
                required=False,
            )

    def get_layout(self):
        fields = ["email", "password", "remember_me"]
        if "next" in self.fields:
            fields.append("next")
        return Layout(
            Section(None, *fields),
            FormActions(
                self.save_label,
                self.cancel_url,
                cancel_label="Forgot password?",
            ),
        )


class SetPasswordForm(BaseForm):
    save_label = "Set password"

    password = forms.CharField(
        label="New password",
        widget=PasswordInput(attrs={"autocomplete": "new-password"}),
        min_length=8,
    )
    confirm_password = forms.CharField(
        label="Confirm password",
        widget=PasswordInput(attrs={"autocomplete": "new-password"}),
        min_length=8,
    )

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get("password")
        confirm = cleaned.get("confirm_password")
        if password and confirm and password != confirm:
            raise ValidationError("Passwords do not match.")
        if password:
            try:
                validate_password(password)
            except ValidationError as exc:
                self.add_error("password", exc)
        return cleaned

    def get_layout(self):
        return Layout(
            Section(None, "password", "confirm_password"),
            FormActions(self.save_label, self.cancel_url),
        )


class ProfileForm(BaseForm, forms.ModelForm):
    save_label = "Save profile"

    class Meta:
        model = User
        fields = ["first_name", "last_name", "phone", "timezone"]

    def __init__(self, *args, user: User, cancel_url=None, **kwargs):
        self.user = user
        self.cancel_url = cancel_url
        kwargs.setdefault("instance", user)
        super().__init__(*args, **kwargs)

    def clean_timezone(self) -> str:
        timezone_value = (self.cleaned_data.get("timezone") or "").strip()
        if timezone_value and timezone_value not in available_timezones():
            raise ValidationError("Select a valid time zone.")
        return timezone_value

    def get_layout(self):
        return Layout(
            Section(None, "first_name", "last_name", "phone", "timezone"),
            FormActions(self.save_label, self.cancel_url),
        )


class ChangePasswordForm(BaseForm):
    save_label = "Change password"

    current_password = forms.CharField(
        label="Current password",
        widget=PasswordInput(attrs={"autocomplete": "current-password"}),
    )
    new_password = forms.CharField(
        label="New password",
        widget=PasswordInput(attrs={"autocomplete": "new-password"}),
        min_length=8,
    )
    confirm_password = forms.CharField(
        label="Confirm new password",
        widget=PasswordInput(attrs={"autocomplete": "new-password"}),
        min_length=8,
    )

    def __init__(self, *args, user: User, cancel_url=None, **kwargs):
        self.user = user
        self.cancel_url = cancel_url
        super().__init__(*args, **kwargs)

    def clean_current_password(self) -> str:
        current = self.cleaned_data.get("current_password", "")
        if not self.user.check_password(current):
            raise ValidationError("Current password is incorrect.")
        return current

    def clean(self):
        cleaned = super().clean()
        new_password = cleaned.get("new_password")
        confirm = cleaned.get("confirm_password")
        if new_password and confirm and new_password != confirm:
            self.add_error("confirm_password", "New passwords do not match.")
            return cleaned
        if new_password:
            try:
                validate_password(new_password, user=self.user)
            except ValidationError as exc:
                self.add_error("new_password", exc)
        return cleaned

    def get_layout(self):
        return Layout(
            Section(None, "current_password", "new_password", "confirm_password"),
            FormActions(self.save_label, self.cancel_url),
        )


class ForgotPasswordForm(BaseForm):
    """Placeholder so PublicFormPage can reuse POST wiring for back navigation."""

    save_label = "Back to sign in"

    def __init__(self, *args, cancel_url=None, **kwargs):
        self.cancel_url = cancel_url
        super().__init__(*args, **kwargs)

    def get_layout(self):
        return Layout(FormActions(self.save_label, self.cancel_url))
