"""Institute settings admin-only view."""

from __future__ import annotations

import pytest
from apps.core.roles import Role
from django.test import Client
from django.urls import reverse
from tests.conftest import make_user


@pytest.mark.django_db
def test_settings_ok_for_institute_admin(client: Client, institute_a) -> None:
    user = make_user(
        email="admin@example.com",
        role=Role.INSTITUTE_ADMIN,
        institute=institute_a,
    )
    client.force_login(user)
    assert client.get(reverse("admin:institute_settings")).status_code == 200


@pytest.mark.django_db
def test_settings_forbidden_for_sub_admin(client: Client, institute_a) -> None:
    user = make_user(
        email="sub@example.com",
        role=Role.SUB_ADMIN,
        institute=institute_a,
    )
    user.allowed_menus = ["institute", "dashboards"]
    client.force_login(user)
    assert client.get(reverse("admin:institute_settings")).status_code == 403


def _settings_payload(**overrides) -> dict[str, str]:
    data = {
        "timezone": "Asia/Karachi",
        "currency_code": "PKR",
        "join_window_minutes": "10",
        "fee_due_day": "10",
        "grace_days_after_due": "5",
        "require_admin_approval_daily_reports": "on",
        "teacher_leave_days_per_year": "12",
        "attendance_present_min_percent": "75",
        "attendance_partial_min_percent": "25",
        "attendance_late_after_minutes": "10",
        "recurring_lecture_horizon_weeks": "8",
    }
    data.update(overrides)
    return data


@pytest.fixture
def admin_client(client: Client, institute_a) -> Client:
    client.force_login(
        make_user(
            email="admin@example.com",
            role=Role.INSTITUTE_ADMIN,
            institute=institute_a,
        )
    )
    return client


@pytest.mark.django_db
def test_settings_save_valid(admin_client: Client, institute_a) -> None:
    response = admin_client.post(
        reverse("admin:institute_settings"),
        _settings_payload(fee_due_day="15", currency_code="USD"),
    )
    assert response.status_code == 302
    institute_a.refresh_from_db()
    assert institute_a.currency_symbol == "$"
    assert institute_a.settings.fee_due_day == 15


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"fee_due_day": "40"}, "between 1 and 28"),
        (
            {
                "attendance_partial_min_percent": "90",
                "attendance_present_min_percent": "75",
            },
            "lower than present",
        ),
        ({"attendance_present_min_percent": "150"}, "0–100%"),
    ],
)
def test_settings_out_of_range_shows_error_not_500(
    admin_client: Client, institute_a, overrides, message
) -> None:
    response = admin_client.post(
        reverse("admin:institute_settings"), _settings_payload(**overrides)
    )
    assert response.status_code == 200
    assert message in response.content.decode()
    institute_a.refresh_from_db()
    assert institute_a.settings.fee_due_day == 10
    assert institute_a.settings.attendance_partial_min_percent == 25
