from __future__ import annotations

import pytest
from apps.core.roles import Role
from apps.core.tenancy import tenant_context
from apps.notifications.services import notify

from tests.conftest import make_user


@pytest.fixture
def people(institute_a, institute_b):
    """Two users of institute A and one of institute B."""
    return {
        "teacher": make_user(
            email="t1@example.com", role=Role.TEACHER, institute=institute_a
        ),
        "student": make_user(
            email="s1@example.com", role=Role.STUDENT, institute=institute_a
        ),
        "admin": make_user(
            email="admin@example.com", role=Role.INSTITUTE_ADMIN, institute=institute_a
        ),
        "other": make_user(
            email="t-b@example.com", role=Role.TEACHER, institute=institute_b
        ),
    }


def send(institute, users, event="new_message", text="Hello.", link="", **kwargs):
    with tenant_context(institute):
        return notify(users, event, text, link, **kwargs)
