"""Portal URL prefixes respond for allowed roles."""

from __future__ import annotations

import pytest
from apps.core.roles import Role
from django.test import Client
from django.urls import reverse

from tests.conftest import make_user

PUBLIC_ALLOWLIST = {
    "accounts:login",
    "accounts:forgot_password",
    "dev_components",
}


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("url_name", "role", "institute_fixture", "expected"),
    [
        ("admin:home", Role.INSTITUTE_ADMIN, "institute_a", 200),
        ("admin:home", Role.TEACHER, "institute_a", 403),
        ("teacher:home", Role.TEACHER, "institute_a", 200),
        ("student:home", Role.STUDENT, "institute_a", 200),
        ("guardian:home", Role.GUARDIAN, "institute_a", 200),
        ("super:institute_list", Role.SUPER_ADMIN, None, 200),
        ("admin:campus", Role.INSTITUTE_ADMIN, "institute_a", 200),
    ],
)
def test_portal_url_access_by_role(
    url_name: str,
    role: str,
    institute_fixture: str | None,
    expected: int,
    request: pytest.FixtureRequest,
) -> None:
    institute = (
        request.getfixturevalue(institute_fixture) if institute_fixture else None
    )
    user = make_user(
        email=f"{role}-walker@example.com",
        role=role,
        institute=institute,
    )
    client = Client()
    client.force_login(user)
    assert client.get(reverse(url_name)).status_code == expected


def test_public_allowlist_names_do_not_require_login() -> None:
    assert "accounts:login" in PUBLIC_ALLOWLIST
