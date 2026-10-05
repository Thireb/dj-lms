"""Tenant middleware sets institute context during the request."""

from __future__ import annotations

import pytest
from apps.core.middleware.tenant import TenantMiddleware
from apps.core.tenancy import get_current_institute
from apps.institutes.models import Institute
from django.test import RequestFactory

from tests.conftest import FakeUser
from tests.testapp.models import TenantProbe


def _noop_response(request):  # noqa: ANN001
    return None


@pytest.mark.django_db
def test_middleware_sets_institute_for_tenant_user(institute_a: Institute) -> None:
    captured: list[Institute | None] = []

    def get_response(request):  # noqa: ANN001
        captured.append(get_current_institute())
        from django.http import HttpResponse

        return HttpResponse("ok")

    request = RequestFactory().get("/")
    request.user = FakeUser(role="institute_admin", institute=institute_a)

    response = TenantMiddleware(get_response)(request)

    assert response.status_code == 200
    assert captured == [institute_a]
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
def test_middleware_scopes_queries_during_request(
    institute_a: Institute,
    institute_b: Institute,
) -> None:
    TenantProbe.objects.create(institute=institute_a, label="a")
    TenantProbe.objects.create(institute=institute_b, label="b")
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
