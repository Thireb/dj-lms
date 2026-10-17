"""Backlog P7-2 (owner decision 2026-10-17): fee dates follow the
institute's calendar, not the viewer's. At 20:00 UTC on 31 Oct it is
already 1 Nov in Karachi (UTC+5) but still 31 Oct in Los Angeles."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from apps.core.tenancy import tenant_context
from apps.core.timezone_utils import institute_today
from apps.finance.services import generate_challans
from django.urls import reverse
from django.utils import timezone

from tests.finance.conftest import add_plan, give_plan
from tests.lectures.conftest import signed_in

MOMENT = datetime(2026, 10, 31, 20, 0, tzinfo=UTC)


@pytest.fixture
def month_end_evening(monkeypatch):
    monkeypatch.setattr(timezone, "now", lambda: MOMENT)


def test_institute_today_uses_the_institute_zone(month_end_evening) -> None:
    class Institute:
        timezone = "Asia/Karachi"

    class Elsewhere:
        timezone = "America/Los_Angeles"

    assert institute_today(Institute()) == date(2026, 11, 1)
    assert institute_today(Elsewhere()) == date(2026, 10, 31)


@pytest.mark.django_db
def test_a_viewer_in_another_zone_sees_the_institute_date(
    fees_school, month_end_evening
) -> None:
    school = fees_school
    institute = school.morning.institute
    assert institute.timezone == "Asia/Karachi"
    give_plan(school.student_1, add_plan(school))
    with tenant_context(institute):
        (challan,) = generate_challans(
            institute,
            date(2026, 10, 1),
            date(2026, 10, 31),
            [school.student_1],
            today=date(2026, 10, 1),
        )
    user = school.student_1.user
    user.timezone = "America/Los_Angeles"
    user.save()
    html = signed_in(user).get(reverse("student:fee_details")).content.decode()
    # Due on 31 Oct; it is 1 Nov at the institute, so it is overdue.
    assert "Overdue" in html


@pytest.mark.django_db
def test_admin_pages_use_the_institute_month(
    fees_school, admin, month_end_evening
) -> None:
    admin.timezone = "America/Los_Angeles"
    admin.save()
    client = signed_in(admin)
    html = client.get(reverse("admin:dashboard_challan")).content.decode()
    assert "Challans for Nov 2026" in html
    html = client.get(reverse("admin:dashboard_main")).content.decode()
    assert "Billed in Nov 2026" in html
