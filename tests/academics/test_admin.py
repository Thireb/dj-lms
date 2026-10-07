"""Developer admin pages for academics (super admin only)."""

from __future__ import annotations

import pytest
from apps.core.roles import Role
from django.apps import apps

from tests.conftest import make_user


@pytest.fixture
def super_client(client):
    user = make_user(
        email="su@example.com",
        role=Role.SUPER_ADMIN,
        is_staff=True,
        is_superuser=True,
    )
    client.force_login(user)
    return client


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("model", "count"),
    [
        ("classlabel", 1),
        ("batch", 3),
        ("subject", 3),
        ("studentbatchsubject", 4),
        ("teacherbatchsubject", 3),
    ],
)
def test_super_admin_sees_changelists(super_client, school, model, count) -> None:
    response = super_client.get(f"/django-admin/academics/{model}/")

    assert response.status_code == 200
    assert response.context["cl"].result_count == count


@pytest.mark.django_db
@pytest.mark.parametrize("model", ["studentbatchsubject", "teacherbatchsubject"])
def test_links_cannot_be_added_or_changed(super_client, school, model) -> None:
    link_model = apps.get_model("academics", model)
    # unscoped: test lookup outside a tenant context.
    pk = link_model.unscoped.values_list("pk", flat=True).first()
    add = super_client.get(f"/django-admin/academics/{model}/add/")
    change = super_client.get(f"/django-admin/academics/{model}/{pk}/change/")

    assert add.status_code == 403
    assert change.status_code == 200
    assert 'name="_save"' not in change.content.decode()


@pytest.mark.django_db
def test_batch_institute_is_read_only_on_change(super_client, school) -> None:
    response = super_client.get(
        f"/django-admin/academics/batch/{school.morning.pk}/change/"
    )

    body = response.content.decode()
    assert response.status_code == 200
    assert 'name="_save"' in body
    assert 'name="institute"' not in body


@pytest.mark.django_db
def test_institute_admin_cannot_open_academics_admin(client, institute_a) -> None:
    user = make_user(
        email="ad@example.com", role=Role.INSTITUTE_ADMIN, institute=institute_a
    )
    client.force_login(user)

    assert client.get("/django-admin/academics/batch/").status_code == 403
