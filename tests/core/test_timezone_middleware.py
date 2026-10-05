"""Timezone middleware activates the user's zone for the request."""

from __future__ import annotations

import pytest
from apps.core.middleware.timezone import TimezoneMiddleware
from apps.core.timezone_utils import resolve_user_timezone
from apps.institutes.models import Institute
from django.test import RequestFactory
from django.utils import timezone

from tests.conftest import FakeUser


@pytest.mark.django_db
def test_resolve_user_timezone_prefers_user_setting(institute_a: Institute) -> None:
    user = FakeUser(role="teacher", institute=institute_a, timezone="America/New_York")
    assert resolve_user_timezone(user) == "America/New_York"


@pytest.mark.django_db
def test_resolve_user_timezone_falls_back_to_institute(
    institute_a: Institute,
) -> None:
    user = FakeUser(role="teacher", institute=institute_a)
    assert resolve_user_timezone(user) == "Asia/Karachi"


@pytest.mark.django_db
def test_middleware_activates_and_deactivates_timezone(
    institute_a: Institute,
) -> None:
    active_during_request: list[str | None] = []

    def get_response(request):  # noqa: ANN001
        active_during_request.append(timezone.get_current_timezone_name())
        from django.http import HttpResponse

        return HttpResponse("ok")

    request = RequestFactory().get("/")
    request.user = FakeUser(role="teacher", institute=institute_a)

    TimezoneMiddleware(get_response)(request)

    assert active_during_request == ["Asia/Karachi"]
    assert timezone.get_current_timezone_name() == "UTC"
