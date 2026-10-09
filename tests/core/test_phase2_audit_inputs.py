"""Phase 2 audit fixes: inputs, admin links, caching, dashboard, admin, root.

Covers M2, M3, M8, M9, L5, L6 and L7.
"""

from __future__ import annotations

import io
import re
from pathlib import Path

import pytest
from apps.accounts.models import SetPasswordToken
from apps.accounts.services import create_set_password_token
from apps.core.query import id_param, search_param
from apps.core.roles import Role
from apps.people.views import AdminDashboardPage
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, RequestFactory
from django.urls import reverse

from tests.conftest import make_user

ROOT = Path(__file__).resolve().parents[2]


def _client(user) -> Client:
    client = Client()
    client.force_login(user)
    return client


@pytest.fixture
def admin(institute_a):
    return make_user(
        email="admin-a@example.com", role=Role.INSTITUTE_ADMIN, institute=institute_a
    )


@pytest.fixture
def super_admin():
    return make_user(email="root@example.com", role=Role.SUPER_ADMIN)


# M3


@pytest.mark.parametrize(
    ("value", "expected"),
    [("12", 12), (" 7 ", 7), ("²", None), ("1²", None), ("-1", None), ("0x1", None),
     ("9" * 19, None), ("9" * 18, 999999999999999999), ("", None), (None, None)],
)  # fmt: skip
def test_id_param(value, expected) -> None:
    assert id_param(value) == expected


def test_search_param() -> None:
    assert search_param("  a\x00b  ") == "ab"
    assert len(search_param("x" * 500)) == 100
    assert search_param(None) == ""


BAD_PARAMS = [
    {"batch": "²"},
    {"class_label": "²"},
    {"q": "a\x00b"},
    {"batch": "9" * 5000},
    {"status": "\x00"},
    {"blocked": "\x00", "exempt": "x" * 5000},
]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "name",
    [
        "admin:student_list",
        "admin:teacher_list",
        "admin:portal_access",
        "admin:batch_list",
        "admin:subject_list",
        "admin:class_list",
    ],
)
@pytest.mark.parametrize("params", BAD_PARAMS)
def test_bad_query_values_never_crash_lists(school, admin, name, params) -> None:
    response = _client(admin).get(reverse(name), params)

    assert response.status_code == 200


@pytest.mark.django_db
def test_super_admin_search_ignores_nul(super_admin, institute_a) -> None:
    response = _client(super_admin).get(reverse("super:institute_list"), {"q": "\x00"})

    assert response.status_code == 200


# M2 and M8


@pytest.mark.django_db
def test_command_prints_a_new_link_and_old_links_stop(admin) -> None:
    old = create_set_password_token(admin).token
    out = io.StringIO()

    call_command(
        "make_set_password_link",
        "ADMIN-A@example.com",
        "--base-url",
        "https://lms.example/",
        stdout=out,
    )

    link = out.getvalue().strip()
    assert re.fullmatch(r"https://lms\.example/accounts/set-password/[\w-]+/", link)
    assert SetPasswordToken.objects.get(pk=old.pk).used_at is not None
    response = Client().get(link.removeprefix("https://lms.example"))
    assert "Set your password" in response.content.decode()


@pytest.mark.django_db
def test_command_refuses_unknown_or_inactive_users(admin) -> None:
    with pytest.raises(CommandError, match="No user"):
        call_command("make_set_password_link", "nobody@example.com")
    admin.is_active = False
    admin.save()
    with pytest.raises(CommandError, match="inactive"):
        call_command("make_set_password_link", admin.email)


@pytest.mark.django_db
def test_super_admin_page_issues_a_new_link(super_admin, admin, institute_a) -> None:
    client = _client(super_admin)
    old = create_set_password_token(admin).token
    edit = client.get(reverse("super:institute_edit", kwargs={"pk": institute_a.pk}))

    response = client.post(
        reverse("super:institute_admin_link", kwargs={"pk": institute_a.pk})
    )
    page = response.content.decode()

    assert "New sign-in link" in edit.content.decode()
    assert "admin-a@example.com" in page
    assert re.search(r"/accounts/set-password/[\w-]+/", page)
    assert "no-store" in response["Cache-Control"]
    assert SetPasswordToken.objects.get(pk=old.pk).used_at is not None


@pytest.mark.django_db
def test_new_link_without_an_admin(super_admin, institute_b) -> None:
    response = _client(super_admin).post(
        reverse("super:institute_admin_link", kwargs={"pk": institute_b.pk})
    )

    assert "This institute has no active admin." in response.content.decode()


@pytest.mark.django_db
def test_new_link_is_post_only_and_super_admin_only(super_admin, admin, institute_a):
    url = reverse("super:institute_admin_link", kwargs={"pk": institute_a.pk})

    assert _client(super_admin).get(url).status_code == 405
    assert _client(admin).post(url).status_code == 403


@pytest.mark.django_db
def test_create_institute_link_page_is_not_cached(super_admin, basic_plan) -> None:
    response = _client(super_admin).post(
        reverse("super:institute_create"),
        {
            "name": "New Institute",
            "plan": basic_plan.pk,
            "admin_email": "first-admin@example.com",
            "admin_first_name": "Sam",
            "admin_last_name": "Sample",
            "timezone": "Asia/Karachi",
            "currency_code": "PKR",
        },
    )

    assert "set-password" in response.content.decode()
    assert "no-store" in response["Cache-Control"]


# M9


@pytest.mark.django_db
def test_dashboard_hides_people_names_without_people_menu(school, institute_a):
    user = make_user(
        email="sub@example.com", role=Role.SUB_ADMIN, institute=institute_a
    )
    user.allowed_menus = ["dashboards"]
    request = RequestFactory().get(reverse("admin:home"))
    request.user = user
    request.institute = institute_a

    page = AdminDashboardPage.as_view()(request).content.decode()

    assert ">Students<" in page  # counts stay
    assert "Recent students" not in page
    assert "s1-a@example.com" not in page


# L5, L6, L7


@pytest.mark.django_db
def test_profile_status_is_read_only_in_developer_admin(school) -> None:
    root = make_user(
        email="dev@example.com", role=Role.SUPER_ADMIN, is_staff=True, is_superuser=True
    )
    url = f"/django-admin/people/studentprofile/{school.student_1.pk}/change/"

    page = _client(root).get(url).content.decode()

    assert 'name="status"' not in page


def test_x_cloak_rule_exists() -> None:
    source = (ROOT / "static/css/src/input.css").read_text()

    assert re.search(r"\[x-cloak\]\s*\{\s*display:\s*none !important;", source)


def test_tailwind_sources_point_inside_the_repo() -> None:
    source = (ROOT / "static/css/src/input.css").read_text()
    base = ROOT / "static/css/src"

    for path in re.findall(r'@source "([^"]+)"', source):
        folder = (base / path.split("**")[0]).resolve()
        assert folder.is_dir() and ROOT in folder.parents, path


@pytest.mark.django_db
def test_root_sends_people_to_the_right_place(institute_a) -> None:
    teacher = make_user(email="t@example.com", role=Role.TEACHER, institute=institute_a)

    anonymous = Client().get("/")
    signed_in = _client(teacher).get("/")

    assert anonymous.status_code == 302
    assert anonymous["Location"] == reverse("accounts:login")
    assert signed_in["Location"] == reverse("teacher:home")
