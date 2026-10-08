"""user_has_menu follows the same rule as MenuRequiredMixin."""

from __future__ import annotations

import pytest
from apps.core.menus import user_has_menu
from apps.core.roles import Role

from tests.conftest import FakeUser


@pytest.mark.parametrize(
    ("role", "menus", "expected"),
    [
        (Role.INSTITUTE_ADMIN, None, True),
        (Role.SUB_ADMIN, ["people"], True),
        (Role.SUB_ADMIN, ["dashboards"], False),
        (Role.SUB_ADMIN, None, False),
        (Role.TEACHER, ["people"], False),
        (Role.SUPER_ADMIN, None, False),
    ],
)
def test_user_has_menu(role, menus, expected) -> None:
    user = FakeUser(role=role, allowed_menus=menus)

    assert user_has_menu(user, "people") is expected
