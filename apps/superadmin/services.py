"""Super Admin institute lifecycle (cross-tenant)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from django.contrib.auth.hashers import make_password
from django.db import transaction
from django.urls import reverse
from django.utils.crypto import get_random_string

from apps.accounts.models import User
from apps.accounts.services import create_set_password_token
from apps.core.roles import Role
from apps.institutes.models import Institute, InstituteSettings, Plan

if TYPE_CHECKING:
    pass


@dataclass(frozen=True)
class CreateInstituteResult:
    institute: Institute
    admin_user: User
    set_password_path: str


@transaction.atomic
def create_institute(
    *,
    name: str,
    plan: Plan,
    admin_email: str,
    timezone: str = "Asia/Karachi",
) -> CreateInstituteResult:
    institute = Institute.objects.create(
        name=name.strip(),
        plan=plan,
        timezone=timezone.strip() or "Asia/Karachi",
        is_active=True,
    )
    InstituteSettings.unscoped.get_or_create(institute=institute)
    admin_user = User.objects.create_user(
        email=admin_email.strip().lower(),
        password=make_password(get_random_string(32)),
        role=Role.INSTITUTE_ADMIN,
        institute=institute,
        timezone=institute.timezone,
    )
    issued = create_set_password_token(admin_user)
    set_password_path = reverse(
        "accounts:set_password",
        kwargs={"token": issued.key},
    )
    return CreateInstituteResult(
        institute=institute,
        admin_user=admin_user,
        set_password_path=set_password_path,
    )


def update_institute(
    institute: Institute,
    *,
    name: str,
    plan: Plan,
    is_active: bool,
) -> Institute:
    institute.name = name.strip()
    institute.plan = plan
    institute.is_active = is_active
    institute.save()
    return institute


def list_institutes():
    return Institute.objects.select_related("plan").order_by("name")
