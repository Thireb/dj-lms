"""Institute campus and settings business logic."""

from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError

from apps.institutes.constants import CURRENCY_SYMBOLS
from apps.institutes.models import Institute, InstituteSettings


def update_campus_profile(
    institute: Institute,
    *,
    name: str,
    address: str,
    phone: str,
    email: str,
) -> Institute:
    institute.name = name.strip()
    institute.address = address.strip()
    institute.phone = phone.strip()
    institute.email = email.strip()
    institute.full_clean()
    institute.save()
    return institute


def validate_settings_ranges(settings: InstituteSettings) -> None:
    errors: dict[str, str] = {}
    if not 1 <= settings.fee_due_day <= 28:
        errors["fee_due_day"] = "Fee due day must be between 1 and 28."
    if settings.join_window_minutes > 120:
        errors["join_window_minutes"] = "Join window cannot exceed 120 minutes."
    if settings.grace_days_after_due > 60:
        errors["grace_days_after_due"] = "Grace days cannot exceed 60."
    if settings.teacher_leave_days_per_year > 365:
        errors["teacher_leave_days_per_year"] = (
            "Leave allowance cannot exceed 365 days."
        )
    if not 0 <= settings.attendance_present_min_percent <= 100:
        errors["attendance_present_min_percent"] = "Present threshold must be 0–100%."
    if not 0 <= settings.attendance_partial_min_percent <= 100:
        errors["attendance_partial_min_percent"] = "Partial threshold must be 0–100%."
    if (
        settings.attendance_partial_min_percent
        >= settings.attendance_present_min_percent
    ):
        errors["attendance_partial_min_percent"] = (
            "Partial threshold must be lower than present threshold."
        )
    if settings.recurring_lecture_horizon_weeks > 52:
        errors["recurring_lecture_horizon_weeks"] = "Horizon cannot exceed 52 weeks."
    if errors:
        raise ValidationError(errors)


def update_institute_settings(
    institute: Institute,
    settings: InstituteSettings,
    *,
    timezone: str,
    currency_code: str,
    **fields: Any,
) -> tuple[Institute, InstituteSettings]:
    institute.timezone = timezone.strip()
    code = currency_code.strip().upper()
    institute.currency_code = code
    institute.currency_symbol = CURRENCY_SYMBOLS.get(code, institute.currency_symbol)
    institute.full_clean()
    institute.save()

    for key, value in fields.items():
        setattr(settings, key, value)
    validate_settings_ranges(settings)
    settings.full_clean()
    settings.save()
    return institute, settings
