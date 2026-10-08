"""Admin main dashboard (roadmap 2.4, SPEC 8)."""

from __future__ import annotations

import pytest
from apps.core.roles import Role
from apps.core.tenancy import tenant_context
from apps.people.dashboard import admin_dashboard
from apps.people.services import set_student_active, set_teacher_active
from apps.people.views import AdminDashboardPage
from django.test import Client, RequestFactory
from django.urls import reverse

from tests.conftest import make_user
from tests.people.conftest import student
from tests.school import link_student


def _admin(institute, role=Role.INSTITUTE_ADMIN):
    return make_user(email=f"{role}@example.com", role=role, institute=institute)


def _deactivate(profile, setter) -> None:
    with tenant_context(profile.institute):
        setter(profile, is_active=False)


@pytest.mark.django_db
def test_counts_are_scoped_to_the_institute(school, institute_a) -> None:
    _deactivate(school.student_2, set_student_active)
    _deactivate(school.teacher_idle, set_teacher_active)

    data = admin_dashboard(_admin(institute_a))

    assert (data.students.total, data.students.active) == (3, 2)
    assert data.students.inactive == 1
    assert data.students.active_percent == 67
    assert (data.teachers.total, data.teachers.active) == (3, 2)
    assert (data.batches_total, data.batches_running) == (2, 1)  # Evening: none


@pytest.mark.django_db
def test_running_batch_counts_once_with_many_active_students(school) -> None:
    link_student(school.student_new, {school.morning: [school.math]})

    data = admin_dashboard(_admin(school.morning.institute))

    assert data.batches_running == 2


@pytest.mark.django_db
def test_recent_lists_are_newest_first_and_capped(school, institute_a) -> None:
    newest = [student(institute_a, f"new{n}@example.com") for n in range(5)]

    data = admin_dashboard(_admin(institute_a))

    assert data.recent_students == list(reversed(newest))
    assert len(data.recent_teachers) == 3


@pytest.mark.django_db
def test_empty_institute_has_zero_counts(institute_b) -> None:
    data = admin_dashboard(_admin(institute_b))

    assert data.students.total == 0
    assert data.students.active_percent == 0


@pytest.mark.django_db
@pytest.mark.parametrize("name", ["admin:home", "admin:dashboard_main"])
def test_dashboard_page_shows_counts_and_recent_people(school, institute_a, name):
    client = Client()
    client.force_login(_admin(institute_a))

    page = client.get(reverse(name)).content.decode()

    assert "Institute A" in page  # hero banner
    assert ">Students<" in page and ">Running batches<" in page
    assert "3 active, 0 inactive" in page
    assert "s1-a@example.com" in page  # recent students (no names in fixture)
    assert "s1-b@example.com" not in page  # institute B
    assert f'href="{reverse("admin:student_list")}"' in page
    for label in ["Enrol student", "Add teacher", "Bulk upload", "Add batch"]:
        assert label in page


@pytest.mark.django_db
def test_sub_admin_sees_only_links_they_can_open(school, institute_a) -> None:
    user = _admin(institute_a, role=Role.SUB_ADMIN)
    user.allowed_menus = ["dashboards", "institute"]
    request = RequestFactory().get(reverse("admin:home"))
    request.user = user
    request.institute = institute_a

    page = AdminDashboardPage.as_view()(request).content.decode()

    assert "Add batch" in page
    assert "Enrol student" not in page
    assert f'href="{reverse("admin:student_list")}"' not in page


@pytest.mark.django_db
def test_sub_admin_without_dashboards_menu_gets_403(institute_a) -> None:
    user = _admin(institute_a, role=Role.SUB_ADMIN)
    user.allowed_menus = ["people"]
    request = RequestFactory().get(reverse("admin:home"))
    request.user = user
    request.institute = institute_a

    assert AdminDashboardPage.as_view()(request).status_code == 403


@pytest.mark.django_db
@pytest.mark.parametrize("role", [Role.TEACHER, Role.STUDENT, Role.GUARDIAN])
def test_other_roles_get_403(client, institute_a, role) -> None:
    client.force_login(
        make_user(email="x@example.com", role=role, institute=institute_a)
    )

    assert client.get(reverse("admin:dashboard_main")).status_code == 403


@pytest.mark.django_db
def test_hero_comes_before_the_stat_cards(school, institute_a) -> None:
    client = Client()
    client.force_login(_admin(institute_a))

    page = client.get(reverse("admin:home")).content.decode()

    assert 0 < page.index("hero-banner") < page.index("stat-card")
