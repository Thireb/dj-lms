"""Account authentication and password-setup business logic."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from django.conf import settings
from django.contrib.auth import authenticate, login
from django.http import HttpRequest
from django.urls import NoReverseMatch, reverse
from django.utils.http import url_has_allowed_host_and_scheme

from apps.accounts.models import SetPasswordToken, User
from apps.core.roles import Role
from apps.ui.menus.registry import build_menu_groups, portal_for_user

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractBaseUser


class TokenStatus(StrEnum):
    OK = "ok"
    MISSING = "missing"
    EXPIRED = "expired"
    USED = "used"


@dataclass(frozen=True)
class TokenLookup:
    status: TokenStatus
    token: SetPasswordToken | None = None


def authenticate_user(*, email: str, password: str) -> User | None:
    user = authenticate(username=email, password=password)
    if user is None or not isinstance(user, User):
        return None
    if not user.is_active:
        return None
    return user


def apply_session_remember_me(request: HttpRequest, *, remember: bool) -> None:
    if remember:
        request.session.set_expiry(settings.SESSION_COOKIE_AGE)
    else:
        request.session.set_expiry(0)


def login_with_remember_me(
    request: HttpRequest, user: AbstractBaseUser, *, remember: bool
) -> None:
    apply_session_remember_me(request, remember=remember)
    login(request, user)


def lookup_set_password_token(key: str) -> TokenLookup:
    if not key:
        return TokenLookup(status=TokenStatus.MISSING)
    try:
        token = SetPasswordToken.objects.select_related("user").get(key=key)
    except SetPasswordToken.DoesNotExist:
        return TokenLookup(status=TokenStatus.MISSING)
    if token.used_at is not None:
        return TokenLookup(status=TokenStatus.USED, token=token)
    if not token.is_valid():
        return TokenLookup(status=TokenStatus.EXPIRED, token=token)
    return TokenLookup(status=TokenStatus.OK, token=token)


def set_password_from_token(*, token: SetPasswordToken, password: str) -> User:
    user = token.user
    user.set_password(password)
    user.save(update_fields=["password"])
    token.mark_used()
    SetPasswordToken.objects.filter(user=user, used_at__isnull=True).exclude(
        pk=token.pk
    ).update(used_at=token.used_at)
    return user


def create_set_password_token(user: User, *, ttl_hours: int = 72) -> SetPasswordToken:
    return SetPasswordToken.create_for_user(user, ttl_hours=ttl_hours)


def _first_menu_url(portal: str, user: User) -> str | None:
    institute = getattr(user, "institute", None)
    groups = build_menu_groups(portal, user, institute)
    for group in groups:
        for item in group.items:
            if not item.disabled and item.url and item.url != "#":
                return item.url
    return None


def post_login_redirect_url(user: User, next_url: str | None = None) -> str:
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={None},
        require_https=getattr(settings, "SECURE_SSL_REDIRECT", False),
    ):
        login_path = reverse("accounts:login")
        if next_url.rstrip("/") != login_path.rstrip("/"):
            return next_url

    portal = portal_for_user(user)
    if portal:
        url = _first_menu_url(portal, user)
        if url:
            return url

    if user.role == Role.SUPER_ADMIN:
        try:
            return reverse("admin:index")
        except NoReverseMatch:
            pass

    return reverse("accounts:login")
