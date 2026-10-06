"""Campus profile and institute settings admin views."""

from __future__ import annotations

from typing import Any

from django.contrib import messages
from django.urls import reverse

from apps.core import menus as menu_keys
from apps.core.roles import Role
from apps.institutes.forms import CampusProfileForm, InstituteSettingsForm
from apps.institutes.models import Institute
from apps.institutes.services import update_campus_profile, update_institute_settings
from apps.ui.views.pages import FormPage


class CampusProfilePage(FormPage):
    portal = "admin"
    menu_key = menu_keys.INSTITUTE
    title = "Campus profile"
    allowed_roles = [Role.INSTITUTE_ADMIN, Role.SUB_ADMIN]
    form_class = CampusProfileForm
    active_item = menu_keys.INSTITUTE

    def get_form_kwargs(self) -> dict[str, Any]:
        institute: Institute = self.get_institute()
        return {"instance": institute}

    def get_success_url(self) -> str:
        return reverse("admin:campus")

    def on_form_valid(self, form: CampusProfileForm) -> None:
        update_campus_profile(
            form.instance,
            name=form.cleaned_data["name"],
            address=form.cleaned_data["address"],
            phone=form.cleaned_data["phone"],
            email=form.cleaned_data["email"],
        )
        messages.success(self.request, "Campus profile updated.")


class InstituteSettingsPage(FormPage):
    portal = "admin"
    admin_only = True
    allowed_roles = [Role.INSTITUTE_ADMIN]
    title = "Institute settings"
    form_class = InstituteSettingsForm
    active_item = "institute_settings"

    def get_form_kwargs(self) -> dict[str, Any]:
        institute: Institute = self.get_institute()
        return {"institute": institute}

    def get_success_url(self) -> str:
        return reverse("admin:institute_settings")

    def on_form_valid(self, form: InstituteSettingsForm) -> None:
        institute = self.get_institute()
        settings = institute.settings
        update_institute_settings(
            institute,
            settings,
            timezone=form.cleaned_data["timezone"],
            currency_code=form.cleaned_data["currency_code"],
            join_window_minutes=form.cleaned_data["join_window_minutes"],
            fee_due_day=form.cleaned_data["fee_due_day"],
            grace_days_after_due=form.cleaned_data["grace_days_after_due"],
            auto_block_defaulters=form.cleaned_data["auto_block_defaulters"],
            auto_approve_guardian_receipts=form.cleaned_data[
                "auto_approve_guardian_receipts"
            ],
            require_admin_approval_homework=form.cleaned_data[
                "require_admin_approval_homework"
            ],
            require_admin_approval_lesson_plans=form.cleaned_data[
                "require_admin_approval_lesson_plans"
            ],
            require_admin_approval_daily_reports=form.cleaned_data[
                "require_admin_approval_daily_reports"
            ],
            teacher_leave_days_per_year=form.cleaned_data[
                "teacher_leave_days_per_year"
            ],
            attendance_present_min_percent=form.cleaned_data[
                "attendance_present_min_percent"
            ],
            attendance_partial_min_percent=form.cleaned_data[
                "attendance_partial_min_percent"
            ],
            attendance_late_after_minutes=form.cleaned_data[
                "attendance_late_after_minutes"
            ],
            lock_course_document_downloads=form.cleaned_data[
                "lock_course_document_downloads"
            ],
            recurring_lecture_horizon_weeks=form.cleaned_data[
                "recurring_lecture_horizon_weeks"
            ],
        )
        messages.success(self.request, "Institute settings updated.")
