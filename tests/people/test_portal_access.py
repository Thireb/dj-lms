"""Portal access: manual block, exemption, Access paused (roadmap 2.7, SPEC 6.2)."""

from __future__ import annotations

import re

import pytest
from apps.core.roles import Role
from apps.core.tenancy import (
    TenantContextError,
    clear_current_institute,
    tenant_context,
)
from apps.people.models import PortalAccessRule
from apps.people.services import (
    list_portal_access,
    set_portal_blocked,
    set_portal_exempt,
    student_portal_blocked,
)
from django.core.exceptions import ValidationError
from django.test import Client
from django.urls import reverse

from tests.conftest import FakeUser, make_user
from tests.people.conftest import account


def _block(student, blocked=True) -> PortalAccessRule:
    with tenant_context(student.institute):
        return set_portal_blocked(student, blocked=blocked)


def _exempt(student, exempt=True) -> PortalAccessRule:
    with tenant_context(student.institute):
        return set_portal_exempt(student, exempt=exempt)


def _client(user) -> Client:
    client = Client()
    client.force_login(user)
    return client


def _admin_client(institute) -> Client:
    return _client(account(institute, "admin-a@example.com", Role.INSTITUTE_ADMIN))


def _codes(response) -> list[str]:
    return re.findall(r">(STU-\d+)<", response.content.decode())


# Services and model


@pytest.mark.django_db
def test_block_and_unblock_keep_one_rule(school) -> None:
    rule = _block(school.student_1)
    again = _block(school.student_1, blocked=False)

    assert rule.pk == again.pk
    assert again.blocked is False
    # unscoped: test assertion outside a tenant context.
    assert PortalAccessRule.unscoped.count() == 1


@pytest.mark.django_db
def test_exempt_does_not_block(school) -> None:
    rule = _exempt(school.student_1)

    assert (rule.blocked, rule.exempt) == (False, True)
    assert student_portal_blocked(school.student_1.user) is False


@pytest.mark.django_db
def test_only_the_blocked_student_is_blocked(school) -> None:
    _block(school.student_1)

    assert student_portal_blocked(school.student_1.user) is True
    assert student_portal_blocked(school.student_2.user) is False


@pytest.mark.django_db
def test_access_services_need_tenant_context(school) -> None:
    with pytest.raises(TenantContextError):
        set_portal_blocked(school.student_1, blocked=True)
    with pytest.raises(TenantContextError):
        set_portal_exempt(school.student_1, exempt=True)


@pytest.mark.django_db
def test_rule_rejects_student_of_other_institute(school, institute_a) -> None:
    with pytest.raises(ValidationError):
        PortalAccessRule(institute=institute_a, student=school.student_b).save()


@pytest.mark.django_db
def test_rule_scopes(school, institute_a, anonymous_user) -> None:
    _block(school.student_1)
    _block(school.student_2)
    _block(school.student_b)

    def visible(user) -> int:
        return PortalAccessRule.objects.for_user(user).count()

    assert visible(account(institute_a, "ad@example.com", Role.INSTITUTE_ADMIN)) == 2
    assert visible(school.student_1.user) == 1
    assert visible(school.guardian_1.user) == 0
    assert visible(school.teacher_1.user) == 0
    assert visible(anonymous_user) == 0
    assert visible(FakeUser(role=Role.INSTITUTE_ADMIN)) == 0
    clear_current_institute()
    assert list(PortalAccessRule.objects.all()) == []


@pytest.mark.django_db
def test_list_filters_treat_no_rule_as_no(school, institute_a) -> None:
    _block(school.student_1)
    _exempt(school.student_2)
    admin = account(institute_a, "ad@example.com", Role.INSTITUTE_ADMIN)

    def codes(**filters) -> list[str]:
        return [s.student_code for s in list_portal_access(admin, **filters)]

    assert codes(blocked="yes") == ["STU-001"]
    assert codes(blocked="no") == ["STU-003", "STU-002"]
    assert codes(exempt="yes") == ["STU-002"]
    assert codes(exempt="no") == ["STU-003", "STU-001"]
    assert len(codes(blocked="maybe")) == 3


# Student portal


@pytest.mark.django_db
def test_blocked_student_sees_access_paused(school, institute_a) -> None:
    institute_a.phone = "042-1234567"
    institute_a.save()
    _block(school.student_1)

    response = _client(school.student_1.user).get(reverse("student:home"))
    page = response.content.decode()

    assert response.status_code == 403
    assert "Access paused. Please contact the institute office at 042-1234567." in page
    assert f'action="{reverse("accounts:logout")}"' in page
    assert 'name="csrfmiddlewaretoken"' in page


@pytest.mark.django_db
def test_message_without_phone(school) -> None:
    _block(school.student_1)

    page = _client(school.student_1.user).get(reverse("student:home"))

    assert "Please contact the institute office." in page.content.decode()


@pytest.mark.django_db
def test_open_and_unblocked_students_see_the_portal(school) -> None:
    _block(school.student_2)
    _block(school.student_2, blocked=False)

    assert (
        _client(school.student_1.user).get(reverse("student:home")).status_code == 200
    )
    assert (
        _client(school.student_2.user).get(reverse("student:home")).status_code == 200
    )


@pytest.mark.django_db
def test_manual_block_wins_over_exemption(school) -> None:
    _exempt(school.student_1)
    _block(school.student_1)

    assert (
        _client(school.student_1.user).get(reverse("student:home")).status_code == 403
    )


@pytest.mark.django_db
def test_blocked_student_can_still_use_account_pages(school) -> None:
    _block(school.student_1)
    client = _client(school.student_1.user)

    assert client.get(reverse("accounts:profile")).status_code == 200
    assert client.post(reverse("accounts:logout")).status_code == 302


@pytest.mark.django_db
def test_guardian_portal_is_never_blocked(school) -> None:
    _block(school.student_1)

    response = _client(school.guardian_1.user).get(reverse("guardian:home"))

    assert response.status_code == 200


# Admin page


@pytest.mark.django_db
def test_admin_page_lists_students_with_access(school, institute_a) -> None:
    _block(school.student_1)
    _exempt(school.student_2)

    page = _admin_client(institute_a).get(reverse("admin:portal_access"))
    html = page.content.decode()

    row = re.search(r">STU-001</td>(.*?)</tr>", html, re.S).group(1)
    assert "g1-a@example.com" in row
    assert ">Yes<" in row and 'value="unblock"' in row and 'value="exempt"' in row
    row_2 = re.search(r">STU-002</td>(.*?)</tr>", html, re.S).group(1)
    assert 'value="block"' in row_2 and 'value="unexempt"' in row_2
    assert ">STU-001<" in html and html.count(">STU-001<") == 1  # not institute B


@pytest.mark.django_db
def test_admin_page_filters(school, institute_a) -> None:
    _block(school.student_1)
    client = _admin_client(institute_a)

    blocked = client.get(reverse("admin:portal_access"), {"blocked": "yes"})
    open_ = client.get(reverse("admin:portal_access"), {"blocked": "no"})

    assert _codes(blocked) == ["STU-001"]
    assert _codes(open_) == ["STU-003", "STU-002"]


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("action", "field", "value", "message"),
    [
        ("block", "blocked", True, "blocked."),
        ("unblock", "blocked", False, "unblocked."),
        ("exempt", "exempt", True, "is exempt."),
        ("unexempt", "exempt", False, "is no longer exempt."),
    ],
)
def test_admin_actions(school, institute_a, action, field, value, message) -> None:
    url = reverse("admin:portal_access_action", kwargs={"pk": school.student_1.pk})

    response = _admin_client(institute_a).post(url, {"action": action}, follow=True)

    # unscoped: test assertion outside a tenant context.
    rule = PortalAccessRule.unscoped.get(student=school.student_1)
    assert getattr(rule, field) is value
    assert message in response.content.decode()


@pytest.mark.django_db
def test_unknown_action_changes_nothing(school, institute_a) -> None:
    url = reverse("admin:portal_access_action", kwargs={"pk": school.student_1.pk})

    response = _admin_client(institute_a).post(url, {"action": "delete"}, follow=True)

    assert "Unknown action." in response.content.decode()
    assert not PortalAccessRule.unscoped.exists()


@pytest.mark.django_db
def test_other_institute_student_is_404(school, institute_a) -> None:
    url = reverse("admin:portal_access_action", kwargs={"pk": school.student_b.pk})

    response = _admin_client(institute_a).post(url, {"action": "block"})

    assert response.status_code == 404
    assert not PortalAccessRule.unscoped.exists()


@pytest.mark.django_db
def test_action_is_post_only(school, institute_a) -> None:
    url = reverse("admin:portal_access_action", kwargs={"pk": school.student_1.pk})

    assert _admin_client(institute_a).get(url).status_code == 405


@pytest.mark.django_db
@pytest.mark.parametrize("role", [Role.TEACHER, Role.STUDENT, Role.GUARDIAN])
def test_other_roles_get_403(client, institute_a, role) -> None:
    client.force_login(
        make_user(email="x@example.com", role=role, institute=institute_a)
    )

    assert client.get(reverse("admin:portal_access")).status_code == 403


@pytest.mark.django_db
def test_sub_admin_without_people_menu_gets_403(client, institute_a) -> None:
    client.force_login(
        make_user(email="sub@example.com", role=Role.SUB_ADMIN, institute=institute_a)
    )

    assert client.get(reverse("admin:portal_access")).status_code == 403


@pytest.mark.django_db
def test_access_paused_page_has_no_empty_header(school) -> None:
    _block(school.student_1)

    page = _client(school.student_1.user).get(reverse("student:home"))

    assert ">None<" not in page.content.decode()
    assert "None" not in re.sub(r"<[^>]+>", " ", page.content.decode()).split()
