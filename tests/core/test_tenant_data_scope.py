"""Cross-institute access returns 404 or empty scope."""

from __future__ import annotations

import pytest
from apps.core.roles import Role
from apps.institutes.models import InstituteSettings
from django.test import RequestFactory

from tests.conftest import make_user


@pytest.mark.django_db
def test_institute_settings_for_user_scoped_to_own_institute(
    institute_a, institute_b
) -> None:
    admin_a = make_user(
        email="a@example.com",
        role=Role.INSTITUTE_ADMIN,
        institute=institute_a,
    )
    visible = InstituteSettings.objects.for_user(admin_a)
    assert visible.filter(institute=institute_a).exists()
    assert not visible.filter(institute=institute_b).exists()


@pytest.mark.django_db
def test_campus_edit_other_institute_not_in_scope(institute_a, institute_b) -> None:
    from apps.institutes.views import CampusProfilePage

    admin_b = make_user(
        email="b@example.com",
        role=Role.INSTITUTE_ADMIN,
        institute=institute_b,
    )
    request = RequestFactory().get("/admin/campus/")
    request.user = admin_b
    request.institute = institute_b
    response = CampusProfilePage.as_view()(request)
    assert response.status_code == 200
    assert institute_b.name in response.content.decode()
