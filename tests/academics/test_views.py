"""Admin pages for classes, batches and subjects (roadmap 2.3b, SPEC 3 and 4.3)."""

from __future__ import annotations

import re

import pytest
from apps.academics.models import Batch, ClassLabel, Subject
from apps.academics.ui import NameListTable
from apps.academics.views import BatchListPage
from apps.core.roles import Role
from django.test import Client, RequestFactory
from django.urls import reverse

from tests.academics.conftest import make_lists
from tests.conftest import make_user

KINDS = [
    pytest.param(ClassLabel, "class", "classes", id="class"),
    pytest.param(Batch, "batch", "batches", id="batch"),
    pytest.param(Subject, "subject", "subjects", id="subject"),
]


@pytest.fixture
def admin_client(client: Client, institute_a) -> Client:
    user = make_user(
        email="admin-a@example.com", role=Role.INSTITUTE_ADMIN, institute=institute_a
    )
    client.force_login(user)
    return client


def _url(prefix: str, action: str, pk: int | None = None) -> str:
    kwargs = {"pk": pk} if pk is not None else None
    return reverse(f"admin:{prefix}_{action}", kwargs=kwargs)


def _rows(model, institute) -> list[str]:
    # unscoped: test assertion outside a tenant context.
    return list(
        model.unscoped.filter(institute=institute).values_list("name", flat=True)
    )


# List


@pytest.mark.django_db
@pytest.mark.parametrize(("model", "prefix", "plural"), KINDS)
def test_empty_list_shows_one_action(admin_client, model, prefix, plural) -> None:
    html = admin_client.get(_url(prefix, "list")).content.decode()

    assert f"No {plural} yet." in html
    assert f"Add your first {prefix}" in html
    assert f'href="{_url(prefix, "create")}"' in html


@pytest.mark.django_db
@pytest.mark.parametrize(("model", "prefix", "plural"), KINDS)
def test_list_shows_own_rows_only(
    admin_client, institute_a, institute_b, model, prefix, plural
) -> None:
    make_lists(institute_a, model, "Own row")
    make_lists(institute_b, model, "Other institute row")

    html = admin_client.get(_url(prefix, "list")).content.decode()

    assert "Own row" in html
    assert "Other institute row" not in html


@pytest.mark.django_db
@pytest.mark.parametrize(("model", "prefix", "plural"), KINDS)
def test_search_filters_by_name(admin_client, institute_a, model, prefix, plural):
    make_lists(institute_a, model, "Alpha", "Beta")

    html = admin_client.get(_url(prefix, "list"), {"q": "alp"}).content.decode()
    empty = admin_client.get(_url(prefix, "list"), {"q": "zzz"}).content.decode()

    assert "Alpha" in html
    assert "Beta" not in html
    assert f"No {plural} match your search." in empty


@pytest.mark.django_db
def test_list_pages_25_rows(admin_client, institute_a) -> None:
    make_lists(institute_a, Batch, *[f"Batch {n:02d}" for n in range(30)])

    first = admin_client.get(_url("batch", "list")).content.decode()
    second = admin_client.get(_url("batch", "list"), {"page": 2}).content.decode()

    assert len(re.findall(r">Batch \d\d<", first)) == 25
    assert len(re.findall(r">Batch \d\d<", second)) == 5


@pytest.mark.django_db
def test_student_count_counts_each_student_once(admin_client, school) -> None:
    html = admin_client.get(_url("batch", "list")).content.decode()

    morning = re.search(r">Morning</td><td[^>]*>(\d+)</td>", html)
    evening = re.search(r">Evening</td><td[^>]*>(\d+)</td>", html)
    assert morning.group(1) == "1"  # one student with two subjects
    assert evening.group(1) == "1"


@pytest.mark.django_db
def test_class_student_count_uses_class_label(admin_client, school) -> None:
    profile = school.student_1
    profile.class_label = school.grade_9
    profile.save()

    html = admin_client.get(_url("class", "list")).content.decode()

    assert re.search(r">Grade 9</td><td[^>]*>1</td>", html)


@pytest.mark.django_db
def test_names_are_escaped(admin_client, institute_a) -> None:
    make_lists(institute_a, Batch, "<script>alert(1)</script>")

    html = admin_client.get(_url("batch", "list")).content.decode()

    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


@pytest.mark.django_db
def test_sub_admin_with_institute_menu_sees_list(institute_a) -> None:
    user = make_user(
        email="sub@example.com", role=Role.SUB_ADMIN, institute=institute_a
    )
    user.allowed_menus = ["institute"]
    request = RequestFactory().get(_url("batch", "list"))
    request.user = user
    request.institute = institute_a

    assert BatchListPage.as_view()(request).status_code == 200


@pytest.mark.django_db
def test_sub_admin_without_institute_menu_gets_403(client, institute_a) -> None:
    user = make_user(
        email="sub@example.com", role=Role.SUB_ADMIN, institute=institute_a
    )
    client.force_login(user)  # test middleware grants only "dashboards"

    assert client.get(_url("batch", "list")).status_code == 403
    assert client.post(_url("batch", "create"), {"name": "X"}).status_code == 403


@pytest.mark.django_db
@pytest.mark.parametrize("role", [Role.TEACHER, Role.STUDENT, Role.GUARDIAN])
def test_other_roles_get_403(client, institute_a, role) -> None:
    client.force_login(
        make_user(email="x@example.com", role=role, institute=institute_a)
    )

    assert client.get(_url("subject", "list")).status_code == 403


# Create


@pytest.mark.django_db
@pytest.mark.parametrize(("model", "prefix", "plural"), KINDS)
def test_create_adds_row(admin_client, institute_a, model, prefix, plural) -> None:
    response = admin_client.post(
        _url(prefix, "create"), {"name": "  Grade   10 "}, follow=True
    )

    assert response.redirect_chain[-1][0] == _url(prefix, "list")
    assert _rows(model, institute_a) == ["Grade 10"]
    assert f"{prefix.capitalize()} added." in response.content.decode()


@pytest.mark.django_db
@pytest.mark.parametrize(("model", "prefix", "plural"), KINDS)
def test_create_rejects_duplicate_ignoring_case(
    admin_client, institute_a, model, prefix, plural
) -> None:
    make_lists(institute_a, model, "Morning")

    response = admin_client.post(_url(prefix, "create"), {"name": "MORNING"})

    assert response.status_code == 200
    assert f"A {prefix} named MORNING already exists." in response.content.decode()
    assert _rows(model, institute_a) == ["Morning"]


@pytest.mark.django_db
def test_create_allows_name_used_by_other_institute(
    admin_client, institute_a, institute_b
) -> None:
    make_lists(institute_b, Batch, "Morning")

    admin_client.post(_url("batch", "create"), {"name": "Morning"})

    assert _rows(Batch, institute_a) == ["Morning"]


@pytest.mark.django_db
def test_create_rejects_blank_name(admin_client, institute_a) -> None:
    response = admin_client.post(_url("batch", "create"), {"name": "   "})

    assert response.status_code == 200
    assert "This field is required." in response.content.decode()
    assert _rows(Batch, institute_a) == []


# Edit


@pytest.mark.django_db
@pytest.mark.parametrize(("model", "prefix", "plural"), KINDS)
def test_edit_renames_row(admin_client, institute_a, model, prefix, plural) -> None:
    (row,) = make_lists(institute_a, model, "Old name")

    page = admin_client.get(_url(prefix, "edit", row.pk))
    response = admin_client.post(_url(prefix, "edit", row.pk), {"name": "New name"})

    assert 'value="Old name"' in page.content.decode()
    assert response.status_code == 302
    assert _rows(model, institute_a) == ["New name"]


@pytest.mark.django_db
def test_edit_may_change_case_of_own_name(admin_client, institute_a) -> None:
    (row,) = make_lists(institute_a, Subject, "maths")

    admin_client.post(_url("subject", "edit", row.pk), {"name": "Maths"})

    assert _rows(Subject, institute_a) == ["Maths"]


@pytest.mark.django_db
def test_edit_rejects_name_of_another_row(admin_client, institute_a) -> None:
    morning, _ = make_lists(institute_a, Batch, "Morning", "Evening")

    response = admin_client.post(_url("batch", "edit", morning.pk), {"name": "evening"})

    assert "A batch named evening already exists." in response.content.decode()
    assert sorted(_rows(Batch, institute_a)) == ["Evening", "Morning"]


@pytest.mark.django_db
@pytest.mark.parametrize(("model", "prefix", "plural"), KINDS)
def test_other_institute_row_is_404(
    admin_client, institute_b, model, prefix, plural
) -> None:
    (row,) = make_lists(institute_b, model, "Theirs")

    assert admin_client.get(_url(prefix, "edit", row.pk)).status_code == 404
    edit = admin_client.post(_url(prefix, "edit", row.pk), {"name": "Mine"})
    status = admin_client.post(_url(prefix, "status", row.pk), {"action": "deactivate"})

    assert edit.status_code == 404
    assert status.status_code == 404
    assert _rows(model, institute_b) == ["Theirs"]
    # unscoped: test assertion outside a tenant context.
    assert model.unscoped.get(pk=row.pk).is_active is True


# Status


@pytest.mark.django_db
@pytest.mark.parametrize(("model", "prefix", "plural"), KINDS)
def test_deactivate_and_activate(admin_client, institute_a, model, prefix, plural):
    (row,) = make_lists(institute_a, model, "Morning")
    url = _url(prefix, "status", row.pk)

    admin_client.post(url, {"action": "deactivate"})
    row.refresh_from_db()
    assert row.is_active is False
    listed = admin_client.get(_url(prefix, "list")).content.decode()
    assert "Inactive" in listed

    response = admin_client.post(url, {"action": "activate"}, follow=True)
    row.refresh_from_db()
    assert row.is_active is True
    assert "Morning activated." in response.content.decode()


@pytest.mark.django_db
def test_unknown_status_action_changes_nothing(admin_client, institute_a) -> None:
    (row,) = make_lists(institute_a, Batch, "Morning")

    response = admin_client.post(
        _url("batch", "status", row.pk), {"action": "delete"}, follow=True
    )

    row.refresh_from_db()
    assert row.is_active is True
    assert "Unknown action." in response.content.decode()


@pytest.mark.django_db
def test_status_is_post_only(admin_client, institute_a) -> None:
    (row,) = make_lists(institute_a, Batch, "Morning")

    assert admin_client.get(_url("batch", "status", row.pk)).status_code == 405


@pytest.mark.django_db
def test_row_dialog_posts_with_csrf_token(institute_a) -> None:
    (row,) = make_lists(institute_a, Batch, "Morning")
    client = Client(enforce_csrf_checks=True)
    client.force_login(
        make_user(
            email="admin-a@example.com",
            role=Role.INSTITUTE_ADMIN,
            institute=institute_a,
        )
    )
    html = client.get(_url("batch", "list")).content.decode()
    status_url = _url("batch", "status", row.pk)
    form = html[html.index(f'action="{status_url}"') :]
    token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', form).group(1)

    without = client.post(status_url, {"action": "deactivate"})
    with_token = client.post(
        status_url, {"action": "deactivate", "csrfmiddlewaretoken": token}
    )

    assert without.status_code == 403
    assert with_token.status_code == 302
    row.refresh_from_db()
    assert row.is_active is False


def test_name_list_table_renders_actions() -> None:
    row = Batch(pk=7, name="Morning", is_active=False)
    row.student_count = 3
    html = str(NameListTable([row], url_prefix="batch", empty_title="None"))

    assert "Morning" in html
    assert ">3<" in html
    assert "Inactive" in html
    assert 'href="/admin/batches/7/edit/"' in html
    assert 'action="/admin/batches/7/status/"' in html
    assert 'value="activate"' in html
