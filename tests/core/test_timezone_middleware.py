"""Timezone middleware activates the user's zone for the request."""

from __future__ import annotations

import pytest
from apps.core.middleware.tenant import TenantMiddleware
from apps.core.middleware.timezone import TimezoneMiddleware
from apps.core.timezone_utils import resolve_user_timezone
from apps.institutes.models import Institute
from django.test import RequestFactory, override_settings
from django.test.utils import CaptureQueriesContext
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
def test_resolve_user_timezone_uses_preloaded_institute(
    institute_a: Institute,
) -> None:
    from django.db import connection

    user = FakeUser(role="teacher", institute_id=institute_a.pk)
    with CaptureQueriesContext(connection) as ctx:
        assert resolve_user_timezone(user, institute=institute_a) == "Asia/Karachi"
    assert len(ctx.captured_queries) == 0


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


@pytest.mark.django_db
@override_settings(MIDDLEWARE=["apps.core.middleware.tenant.TenantMiddleware"])
def test_timezone_middleware_reuses_request_institute_no_extra_query(
    institute_a: Institute,
) -> None:
    active_during_request: list[str | None] = []

    def get_response(request):  # noqa: ANN001
        active_during_request.append(timezone.get_current_timezone_name())
        from django.http import HttpResponse

        return HttpResponse("ok")

    request = RequestFactory().get("/")
    request.user = FakeUser(role="teacher", institute_id=institute_a.pk)

    def stack(request):  # noqa: ANN001
        tenant_response = TenantMiddleware(
            lambda r: TimezoneMiddleware(get_response)(r)
        )(request)
        return tenant_response

    from django.db import connection

    with CaptureQueriesContext(connection) as ctx:
        stack(request)

    institute_selects = [
        q for q in ctx.captured_queries if "institutes_institute" in q["sql"].lower()
    ]
    assert len(institute_selects) == 1
    assert active_during_request == ["Asia/Karachi"]
