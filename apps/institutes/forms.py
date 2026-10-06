"""Campus profile and institute settings forms."""

from __future__ import annotations

from zoneinfo import available_timezones

from crispy_forms.layout import Layout
from django import forms
from django.core.exceptions import ValidationError

from apps.institutes.constants import CURRENCY_CHOICES
from apps.institutes.models import Institute, InstituteSettings
from apps.ui.forms.base import BaseForm, TenantModelForm
from apps.ui.forms.layout import FormActions, Section


class CampusProfileForm(BaseForm, forms.ModelForm):
    save_label = "Save campus profile"

    class Meta:
        model = Institute
        fields = ["name", "address", "phone", "email"]

    def get_layout(self):
        return Layout(
            Section(None, "name", "address", "phone", "email"),
            FormActions(self.save_label, self.cancel_url),
        )


class InstituteSettingsForm(TenantModelForm, forms.ModelForm):
    save_label = "Save institute settings"

    timezone = forms.CharField(label="Time zone", max_length=63)
    currency_code = forms.ChoiceField(
        label="Currency code",
        choices=CURRENCY_CHOICES,
    )

    class Meta:
        model = InstituteSettings
        fields = [
            "join_window_minutes",
            "fee_due_day",
            "grace_days_after_due",
            "auto_block_defaulters",
            "auto_approve_guardian_receipts",
            "require_admin_approval_homework",
            "require_admin_approval_lesson_plans",
            "require_admin_approval_daily_reports",
            "teacher_leave_days_per_year",
            "attendance_present_min_percent",
            "attendance_partial_min_percent",
            "attendance_late_after_minutes",
            "lock_course_document_downloads",
            "recurring_lecture_horizon_weeks",
        ]

    def __init__(self, *args, institute: Institute, **kwargs):
        self.institute = institute
        kwargs.setdefault("instance", institute.settings)
        super().__init__(*args, institute=institute, **kwargs)
        self.fields["timezone"].initial = institute.timezone
        self.fields["currency_code"].initial = institute.currency_code

    def clean_timezone(self) -> str:
        timezone_value = (self.cleaned_data.get("timezone") or "").strip()
        if timezone_value and timezone_value not in available_timezones():
            raise ValidationError("Select a valid time zone.")
        return timezone_value

    def get_layout(self):
        return Layout(
            Section(
                "Regional",
                "timezone",
                "currency_code",
            ),
            Section(
                "Fees and portal",
                "join_window_minutes",
                "fee_due_day",
                "grace_days_after_due",
                "auto_block_defaulters",
                "auto_approve_guardian_receipts",
            ),
            Section(
                "Approvals",
                "require_admin_approval_homework",
                "require_admin_approval_lesson_plans",
                "require_admin_approval_daily_reports",
            ),
            Section(
                "Attendance and content",
                "teacher_leave_days_per_year",
                "attendance_present_min_percent",
                "attendance_partial_min_percent",
                "attendance_late_after_minutes",
                "lock_course_document_downloads",
                "recurring_lecture_horizon_weeks",
            ),
            FormActions(self.save_label, self.cancel_url),
        )
