from __future__ import annotations

import pytest
from apps.core.roles import Role
from apps.core.tenancy import tenant_context

from tests.conftest import make_user


@pytest.fixture
def admin(school):
    return make_user(
        email="admin-a@example.com",
        role=Role.INSTITUTE_ADMIN,
        institute=school.morning.institute,
    )


def run(school, function, *args, **kwargs):
    with tenant_context(school.morning.institute):
        return function(*args, **kwargs)
