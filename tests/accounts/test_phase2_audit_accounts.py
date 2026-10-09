"""Phase 2 audit fixes for sign-in and accounts (H1, H2, L1, L2, L3, L8-L10)."""

from __future__ import annotations

from unittest import mock

import pytest
from apps.accounts.models import SetPasswordToken, User
from apps.accounts.services import create_set_password_token, set_password_from_token
from apps.accounts.throttle import FAILURE_LIMIT, LOCKED_MESSAGE
from apps.core.roles import Role
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import Client
from django.urls import reverse

from tests.conftest import (
    TEST_LOGIN_PASSWORD,
    TEST_NEW_PASSWORD,
    TEST_WRONG_LOGIN_PASSWORD,
    make_user,
)


def _login(client: Client, email: str, password: str, **extra):
    return client.post(
        reverse("accounts:login"), {"email": email, "password": password}, **extra
    )


def _fail(client: Client, email: str, times: int = FAILURE_LIMIT, **extra) -> None:
    for _ in range(times):
        _login(client, email, TEST_WRONG_LOGIN_PASSWORD, **extra)


@pytest.fixture
def teacher(institute_a) -> User:
    return make_user(email="sam@example.com", role=Role.TEACHER, institute=institute_a)


# H1: sign-in limits


@pytest.mark.django_db
def test_sixth_attempt_is_refused_even_with_the_right_password(client, teacher):
    _fail(client, "sam@example.com")

    response = _login(client, "sam@example.com", TEST_LOGIN_PASSWORD)

    assert response.status_code == 429
    assert LOCKED_MESSAGE in response.content.decode()
    assert not response.wsgi_request.user.is_authenticated


@pytest.mark.django_db
def test_locked_sign_in_does_not_hash_a_password(client, teacher) -> None:
    _fail(client, "sam@example.com")

    with mock.patch("apps.accounts.views.authenticate_user") as auth:
        _login(client, "sam@example.com", TEST_LOGIN_PASSWORD)

    auth.assert_not_called()


@pytest.mark.django_db
def test_four_failures_still_allow_sign_in_and_reset_the_count(client, teacher):
    _fail(client, "sam@example.com", times=FAILURE_LIMIT - 1)
    assert _login(client, "sam@example.com", TEST_LOGIN_PASSWORD).status_code == 302

    client.post(reverse("accounts:logout"))
    _fail(client, "sam@example.com", times=FAILURE_LIMIT - 1)
    assert _login(client, "sam@example.com", TEST_LOGIN_PASSWORD).status_code == 302


@pytest.mark.django_db
def test_limit_is_per_email_ignoring_case(client, teacher) -> None:
    _fail(client, "SAM@example.com")

    other = _login(client, "someone@example.com", TEST_WRONG_LOGIN_PASSWORD)
    same = _login(client, "Sam@Example.com", TEST_LOGIN_PASSWORD)

    assert other.status_code == 200
    assert same.status_code == 429


@pytest.mark.django_db
def test_limit_is_per_ip(client, teacher) -> None:
    _fail(client, "sam@example.com", REMOTE_ADDR="10.0.0.1")

    other_ip = _login(
        client, "sam@example.com", TEST_LOGIN_PASSWORD, REMOTE_ADDR="10.0.0.2"
    )

    assert other_ip.status_code == 302


@pytest.mark.django_db
def test_proxy_header_is_used_only_when_trusted(client, teacher, settings) -> None:
    _fail(client, "sam@example.com", HTTP_X_REAL_IP="1.1.1.1")
    forged = _login(
        client, "sam@example.com", TEST_LOGIN_PASSWORD, HTTP_X_REAL_IP="2.2.2.2"
    )
    assert forged.status_code == 429  # header ignored: same REMOTE_ADDR

    settings.TRUSTED_PROXY_IP_HEADER = "HTTP_X_REAL_IP"
    trusted = _login(
        client, "sam@example.com", TEST_LOGIN_PASSWORD, HTTP_X_REAL_IP="2.2.2.2"
    )
    assert trusted.status_code == 302


@pytest.mark.django_db
def test_developer_admin_login_shares_the_limit(client) -> None:
    make_user(
        email="root@example.com",
        role=Role.SUPER_ADMIN,
        is_staff=True,
        is_superuser=True,
    )
    _fail(client, "root@example.com")

    response = client.post(
        reverse("developer:login"),
        {"username": "root@example.com", "password": TEST_LOGIN_PASSWORD},
    )

    assert LOCKED_MESSAGE in response.content.decode()
    assert not response.wsgi_request.user.is_authenticated


@pytest.mark.django_db
def test_developer_admin_failures_count_for_the_product_login(client) -> None:
    make_user(email="root@example.com", role=Role.SUPER_ADMIN, is_superuser=True)
    for _ in range(FAILURE_LIMIT):
        client.post(
            reverse("developer:login"),
            {"username": "root@example.com", "password": TEST_WRONG_LOGIN_PASSWORD},
        )

    assert _login(client, "root@example.com", TEST_LOGIN_PASSWORD).status_code == 429


@pytest.mark.django_db
def test_set_password_page_is_limited(client, teacher) -> None:
    key = create_set_password_token(teacher).key
    url = reverse("accounts:set_password", kwargs={"token": key})
    for _ in range(FAILURE_LIMIT):
        client.post(url, {"password": "short", "confirm_password": "short"})

    response = client.post(
        url, {"password": TEST_NEW_PASSWORD, "confirm_password": TEST_NEW_PASSWORD}
    )

    assert response.status_code == 429
    teacher.refresh_from_db()
    assert teacher.check_password(TEST_LOGIN_PASSWORD)


@pytest.mark.django_db
def test_wrong_set_password_links_count_as_failures(client, teacher) -> None:
    bad = reverse("accounts:set_password", kwargs={"token": "not-a-real-token"})
    for _ in range(FAILURE_LIMIT):
        client.post(bad, {"password": "x", "confirm_password": "x"})
    good = reverse(
        "accounts:set_password",
        kwargs={"token": create_set_password_token(teacher).key},
    )

    response = client.post(
        good, {"password": TEST_NEW_PASSWORD, "confirm_password": TEST_NEW_PASSWORD}
    )

    assert response.status_code == 429


# H2: email case


@pytest.mark.django_db
def test_email_is_stored_lower_case_and_sign_in_ignores_case(client, institute_a):
    user = make_user(
        email=" Sam@Example.COM ", role=Role.TEACHER, institute=institute_a
    )

    assert user.email == "sam@example.com"
    for typed in ["sam@example.com", "Sam@Example.com", "SAM@EXAMPLE.COM"]:
        client.post(reverse("accounts:logout"))
        assert _login(client, typed, TEST_LOGIN_PASSWORD).status_code == 302, typed


@pytest.mark.django_db
def test_saving_lower_cases_the_email(institute_a) -> None:
    user = make_user(email="sam@example.com", role=Role.TEACHER, institute=institute_a)
    user.email = "New.Address@Example.com"
    user.save()

    user.refresh_from_db()
    assert user.email == "new.address@example.com"


@pytest.mark.django_db
def test_two_accounts_cannot_differ_only_by_case(institute_a) -> None:
    user = make_user(email="sam@example.com", role=Role.TEACHER, institute=institute_a)
    User.objects.filter(pk=user.pk).update(email="Sam@example.com")  # old data

    with pytest.raises((ValidationError, IntegrityError)), transaction.atomic():
        make_user(email="sam@example.com", role=Role.STUDENT, institute=institute_a)


@pytest.mark.django_db
def test_database_constraint_blocks_case_duplicates(institute_a) -> None:
    make_user(email="sam@example.com", role=Role.TEACHER, institute=institute_a)
    other = make_user(
        email="other@example.com", role=Role.TEACHER, institute=institute_a
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        User.objects.filter(pk=other.pk).update(email="SAM@example.com")


@pytest.mark.django_db
def test_migration_lower_cases_old_emails(institute_a) -> None:
    from importlib import import_module

    from django.apps import apps

    migration = import_module("apps.accounts.migrations.0005_lowercase_emails")
    user = make_user(email="sam@example.com", role=Role.TEACHER, institute=institute_a)
    User.objects.filter(pk=user.pk).update(email="Sam@Example.com")

    migration.lowercase_emails(apps, None)

    user.refresh_from_db()
    assert user.email == "sam@example.com"


# L1, L2, L3, L8, L9, L10


@pytest.mark.django_db
def test_inactive_institute_page_has_a_sign_out_button(client, teacher, institute_a):
    client.force_login(teacher)
    institute_a.is_active = False
    institute_a.save()

    response = client.get(reverse("teacher:home"))
    page = response.content.decode()

    assert response.status_code == 403
    assert "Your institute is not active." in page
    assert f'action="{reverse("accounts:logout")}"' in page
    assert 'name="csrfmiddlewaretoken"' in page


@pytest.mark.django_db
def test_session_without_remember_me_ends_on_server_too(client, teacher, settings):
    _login(client, "sam@example.com", TEST_LOGIN_PASSWORD)
    short = client.session

    client.post(reverse("accounts:logout"))
    client.post(
        reverse("accounts:login"),
        {"email": "sam@example.com", "password": TEST_LOGIN_PASSWORD, "remember_me": 1},
    )
    long = client.session

    assert short.get_expire_at_browser_close() is True
    assert short.get_expiry_age() == 12 * 60 * 60
    assert long.get_expire_at_browser_close() is False
    assert long.get_expiry_age() == settings.REMEMBER_ME_SECONDS


@pytest.mark.django_db
def test_password_spaces_are_kept(client, institute_a) -> None:
    spaced = f" {TEST_LOGIN_PASSWORD} "
    make_user(
        email="sam@example.com",
        role=Role.TEACHER,
        institute=institute_a,
        password=spaced,
    )

    assert _login(client, "sam@example.com", TEST_LOGIN_PASSWORD).status_code == 200
    assert _login(client, "sam@example.com", spaced).status_code == 302


def test_every_password_field_keeps_spaces() -> None:
    from apps.accounts import forms
    from apps.people.forms import StudentEnrolForm, TeacherCreateForm

    classes = [
        forms.LoginForm,
        forms.SetPasswordForm,
        forms.ChangePasswordForm,
        StudentEnrolForm,
        TeacherCreateForm,
    ]
    for form_class in classes:
        for name, field in form_class.base_fields.items():
            if "password" in name:
                assert field.strip is False, f"{form_class.__name__}.{name}"


@pytest.mark.django_db
def test_create_user_super_admin_can_use_developer_admin() -> None:
    user = User.objects.create_user(
        email="root@example.com", password=TEST_LOGIN_PASSWORD, role=Role.SUPER_ADMIN
    )

    assert user.is_staff is True


@pytest.mark.django_db
def test_a_token_is_used_only_once(teacher) -> None:
    token = create_set_password_token(teacher).token

    first = set_password_from_token(token=token, password=TEST_NEW_PASSWORD)
    second = set_password_from_token(token=token, password=TEST_LOGIN_PASSWORD)

    assert first == teacher
    assert second is None
    teacher.refresh_from_db()
    assert teacher.check_password(TEST_NEW_PASSWORD)
    assert SetPasswordToken.objects.get(pk=token.pk).used_at is not None


@pytest.mark.django_db
def test_link_used_in_another_tab_shows_used_page(client, teacher) -> None:
    created = create_set_password_token(teacher)
    url = reverse("accounts:set_password", kwargs={"token": created.key})
    client.get(url)
    set_password_from_token(token=created.token, password=TEST_NEW_PASSWORD)

    response = client.post(
        url, {"password": TEST_LOGIN_PASSWORD, "confirm_password": TEST_LOGIN_PASSWORD}
    )

    assert "already used" in response.content.decode()


@pytest.mark.django_db
def test_set_password_rejects_a_password_like_the_email(client, institute_a) -> None:
    user = make_user(
        email="kinza.placeholder@example.com",
        role=Role.TEACHER,
        institute=institute_a,
    )
    url = reverse(
        "accounts:set_password", kwargs={"token": create_set_password_token(user).key}
    )

    response = client.post(
        url,
        {
            "password": "kinza.placeholder",
            "confirm_password": "kinza.placeholder",
        },
    )

    assert "too similar" in response.content.decode()
