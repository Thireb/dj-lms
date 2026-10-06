"""Account service helpers (redirects and password validation)."""

from __future__ import annotations

import pytest
from apps.accounts.forms import SetPasswordForm
from apps.accounts.models import SetPasswordToken
from apps.accounts.services import (
    INACTIVE_INSTITUTE_LOGIN_MESSAGE,
    TokenStatus,
    authenticate_user,
    create_set_password_token,
    lookup_set_password_token,
    post_login_redirect_url,
)
from apps.core.roles import Role
from django.urls import reverse

from tests.conftest import (
    TEST_INVALID_PASSWORD_FOR_VALIDATION,
    TEST_LOGIN_PASSWORD,
    make_user,
)


@pytest.mark.django_db
def test_post_login_never_returns_login_url(institute_a) -> None:
    user = make_user(
        email="teacher@example.com",
        role=Role.TEACHER,
        institute=institute_a,
    )
    url = post_login_redirect_url(user, next_url=reverse("accounts:login"))
    assert url.rstrip("/") != reverse("accounts:login").rstrip("/")


@pytest.mark.django_db
def test_post_login_skips_post_only_menu_items(institute_a) -> None:
    user = make_user(
        email="teacher@example.com",
        role=Role.TEACHER,
        institute=institute_a,
    )
    url = post_login_redirect_url(user)
    assert url == reverse("accounts:teacher_home")


@pytest.mark.django_db
def test_set_password_token_stores_hash_not_plaintext(institute_a) -> None:
    user = make_user(
        email="student@example.com",
        role=Role.STUDENT,
        institute=institute_a,
    )
    issued = create_set_password_token(user)
    assert issued.key != issued.token.key
    assert issued.token.key == SetPasswordToken.hash_key(issued.key)
    lookup = lookup_set_password_token(issued.key)
    assert lookup.status == TokenStatus.OK
    assert lookup.token is not None
    assert lookup.token.pk == issued.token.pk


@pytest.mark.django_db
def test_authenticate_rejects_inactive_institute(institute_a) -> None:
    institute_a.is_active = False
    institute_a.save(update_fields=["is_active"])
    make_user(
        email="teacher@example.com",
        role=Role.TEACHER,
        institute=institute_a,
    )
    result = authenticate_user(
        email="teacher@example.com",
        password=TEST_LOGIN_PASSWORD,
    )
    assert result.user is None
    assert result.error == INACTIVE_INSTITUTE_LOGIN_MESSAGE


@pytest.mark.django_db
def test_authenticate_allows_super_admin_without_institute() -> None:
    from apps.accounts.models import User

    User.objects.create_superuser(
        email="super@example.com",
        password=TEST_LOGIN_PASSWORD,
    )
    result = authenticate_user(
        email="super@example.com",
        password=TEST_LOGIN_PASSWORD,
    )
    assert result.user is not None
    assert result.error is None


@pytest.mark.django_db
def test_set_password_form_calls_validate_password() -> None:
    form = SetPasswordForm(
        data={
            "password": TEST_INVALID_PASSWORD_FOR_VALIDATION,
            "confirm_password": TEST_INVALID_PASSWORD_FOR_VALIDATION,
        },
    )
    assert not form.is_valid()
    assert form.errors
