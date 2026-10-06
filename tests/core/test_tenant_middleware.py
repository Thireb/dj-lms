"""Tenant middleware sets institute context during the request."""

from __future__ import annotations

import pytest
from apps.core.middleware.tenant import TenantMiddleware
from apps.core.tenancy import get_current_institute
from apps.institutes.models import Institute
from django.test import RequestFactory

from tests.conftest import FakeUser
from tests.testapp.models import TenantProbe


@pytest.mark.django_db
def test_middleware_sets_institute_for_tenant_user(institute_a: Institute) -> None:
    captured: list[Institute | None] = []
    request_institutes: list[Institute | None] = []

    def get_response(request):  # noqa: ANN001
        captured.append(get_current_institute())
        request_institutes.append(getattr(request, "institute", None))
        from django.http import HttpResponse

        return HttpResponse("ok")

    request = RequestFactory().get("/")
    request.user = FakeUser(role="institute_admin", institute=institute_a)

    response = TenantMiddleware(get_response)(request)

    assert response.status_code == 200
    assert captured == [institute_a]
    assert request_institutes == [institute_a]
    assert get_current_institute() is None


@pytest.mark.django_db
def test_middleware_clears_context_for_super_admin(institute_a: Institute) -> None:
    captured: list[Institute | None] = []

    def get_response(request):  # noqa: ANN001
        captured.append(get_current_institute())
        from django.http import HttpResponse

        return HttpResponse("ok")

    request = RequestFactory().get("/")
    request.user = FakeUser(role="super_admin", institute_id=None)

    TenantMiddleware(get_response)(request)

    assert captured == [None]


@pytest.mark.django_db
def test_middleware_forbidden_without_institute_id() -> None:
    def get_response(request):  # noqa: ANN001
        pytest.fail("get_response should not run")

    request = RequestFactory().get("/")
    request.user = FakeUser(role="teacher", institute_id=None)

    response = TenantMiddleware(get_response)(request)

    assert response.status_code == 403


@pytest.mark.django_db
def test_middleware_allows_logout_without_institute_id() -> None:
    reached: list[bool] = []

    def get_response(request):  # noqa: ANN001
        reached.append(True)
        from django.http import HttpResponse

        return HttpResponse("ok")

    request = RequestFactory().get("/accounts/logout/")
    request.user = FakeUser(role="teacher", institute_id=None)

    response = TenantMiddleware(get_response)(request)

    assert response.status_code == 200
    assert reached == [True]


@pytest.mark.django_db
def test_middleware_allows_logout_when_institute_inactive(
    institute_a: Institute,
) -> None:
    institute_a.is_active = False
    institute_a.save(update_fields=["is_active"])
    reached: list[bool] = []

    def get_response(request):  # noqa: ANN001
        reached.append(True)
        from django.http import HttpResponse

        return HttpResponse("ok")

    request = RequestFactory().get("/accounts/logout/")
    request.user = FakeUser(role="teacher", institute=institute_a)

    response = TenantMiddleware(get_response)(request)

    assert response.status_code == 200
    assert reached == [True]


@pytest.mark.django_db
def test_middleware_allows_logout_when_institute_missing() -> None:
    reached: list[bool] = []

    def get_response(request):  # noqa: ANN001
        reached.append(True)
        from django.http import HttpResponse

        return HttpResponse("ok")

    request = RequestFactory().get("/accounts/logout/")
    request.user = FakeUser(role="teacher", institute_id=999_999)

    response = TenantMiddleware(get_response)(request)

    assert response.status_code == 200
    assert reached == [True]


@pytest.mark.django_db
def test_middleware_inactive_institute_forbidden(institute_a: Institute) -> None:
    institute_a.is_active = False
    institute_a.save(update_fields=["is_active"])

    def get_response(request):  # noqa: ANN001
        pytest.fail("get_response should not run")

    request = RequestFactory().get("/")
    request.user = FakeUser(role="teacher", institute=institute_a)

    response = TenantMiddleware(get_response)(request)

    assert response.status_code == 403


@pytest.mark.django_db
def test_middleware_active_institute_ok(institute_a: Institute) -> None:
    def get_response(request):  # noqa: ANN001
        from django.http import HttpResponse

        return HttpResponse("ok")

    request = RequestFactory().get("/")
    request.user = FakeUser(role="teacher", institute=institute_a)

    response = TenantMiddleware(get_response)(request)

    assert response.status_code == 200


@pytest.mark.django_db
def test_middleware_inactive_institute_mid_session(
    institute_a: Institute,
) -> None:
    def get_response(request):  # noqa: ANN001
        from django.http import HttpResponse

        return HttpResponse("ok")

    request = RequestFactory().get("/")
    request.user = FakeUser(role="teacher", institute=institute_a)

    assert TenantMiddleware(get_response)(request).status_code == 200

    institute_a.is_active = False
    institute_a.save(update_fields=["is_active"])

    assert TenantMiddleware(get_response)(request).status_code == 403


@pytest.mark.django_db
def test_middleware_super_admin_ok_when_institute_inactive(
    institute_a: Institute,
) -> None:
    institute_a.is_active = False
    institute_a.save(update_fields=["is_active"])

    def get_response(request):  # noqa: ANN001
        from django.http import HttpResponse

        return HttpResponse("ok")

    request = RequestFactory().get("/")
    request.user = FakeUser(role="super_admin", institute_id=None)

    response = TenantMiddleware(get_response)(request)

    assert response.status_code == 200


@pytest.mark.django_db
def test_middleware_forbidden_when_institute_missing() -> None:
    def get_response(request):  # noqa: ANN001
        pytest.fail("get_response should not run")

    request = RequestFactory().get("/")
    request.user = FakeUser(role="teacher", institute_id=999_999)

    response = TenantMiddleware(get_response)(request)

    assert response.status_code == 403


@pytest.mark.django_db
def test_middleware_scopes_queries_during_request(
    institute_a: Institute,
    institute_b: Institute,
) -> None:
    TenantProbe.unscoped.create(institute=institute_a, label="a")
    TenantProbe.unscoped.create(institute=institute_b, label="b")
    seen_labels: list[str] = []

    def get_response(request):  # noqa: ANN001
        seen_labels.extend(
            TenantProbe.objects.order_by("label").values_list("label", flat=True)
        )
        from django.http import HttpResponse

        return HttpResponse("ok")

    request = RequestFactory().get("/")
    request.user = FakeUser(role="teacher", institute=institute_a)

    TenantMiddleware(get_response)(request)

    assert seen_labels == ["a"]
