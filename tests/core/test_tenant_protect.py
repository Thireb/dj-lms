"""Institute PROTECT and anonymous for_user edge cases."""

from __future__ import annotations

import pytest
from apps.institutes.models import Institute
from django.db.models import ProtectedError

from tests.conftest import FakeUser
from tests.testapp.models import TenantProbe


@pytest.mark.django_db
def test_protect_blocks_deleting_institute_with_tenant_data(
    institute_a: Institute,
    probe_a: TenantProbe,
) -> None:
    with pytest.raises(ProtectedError):
        institute_a.delete()


@pytest.mark.django_db
def test_anonymous_user_with_institute_id_gets_nothing_from_for_user(
    institute_a: Institute,
    probe_a: TenantProbe,
) -> None:
    user = FakeUser(
        role="",
        institute_id=institute_a.pk,
        is_authenticated=False,
    )
    assert list(TenantProbe.objects.for_user(user)) == []
