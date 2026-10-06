"""Account service helpers (redirects and password validation)."""

from __future__ import annotations

import pytest
from apps.accounts.forms import SetPasswordForm
from apps.accounts.services import post_login_redirect_url
from apps.core.roles import Role
from django.urls import reverse

from tests.conftest import make_user


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
def test_set_password_form_calls_validate_password() -> None:
    form = SetPasswordForm(
        data={"password": "password", "confirm_password": "password"},
    )
    assert not form.is_valid()
    assert form.errors
