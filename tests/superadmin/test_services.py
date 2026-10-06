"""Super Admin institute services."""

from __future__ import annotations

import pytest
from apps.accounts.models import SetPasswordToken, User
from apps.core.roles import Role
from apps.institutes.models import Institute, InstituteSettings
from apps.superadmin.services import create_institute, list_institutes


@pytest.mark.django_db
def test_create_institute_transaction(basic_plan) -> None:
    result = create_institute(
        name="Tx Institute",
        plan=basic_plan,
        admin_email="tx-admin@example.com",
    )
    assert result.set_password_path.startswith("/accounts/set-password/")
    assert Institute.objects.filter(pk=result.institute.pk).exists()
    assert InstituteSettings.unscoped.filter(institute=result.institute).exists()
    assert User.objects.filter(email="tx-admin@example.com", role=Role.INSTITUTE_ADMIN)
    assert SetPasswordToken.objects.filter(user=result.admin_user).exists()


@pytest.mark.django_db
def test_list_institutes_includes_all_tenants(institute_a, institute_b) -> None:
    names = {i.name for i in list_institutes()}
    assert "Institute A" in names
    assert "Institute B" in names
