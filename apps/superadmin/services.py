"""Super Admin institute lifecycle (cross-tenant)."""

from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction
from django.db.models import Count, Q, QuerySet
from django.urls import reverse

from apps.accounts.models import User
from apps.accounts.services import create_set_password_token
from apps.core.roles import Role
from apps.institutes.constants import CURRENCY_SYMBOLS
from apps.institutes.models import Institute, Plan


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
    admin_first_name: str = "",
    admin_last_name: str = "",
    timezone: str = "Asia/Karachi",
    currency_code: str = "PKR",
) -> CreateInstituteResult:
    """Create the institute, its settings row (signal) and first admin, atomically."""
    institute = Institute.objects.create(
        name=name.strip(),
        plan=plan,
        timezone=timezone.strip() or "Asia/Karachi",
        currency_code=currency_code,
        currency_symbol=CURRENCY_SYMBOLS.get(currency_code, ""),
        is_active=True,
    )
    admin_user = User.objects.create_user(
        email=admin_email.strip().lower(),
        password=None,
        role=Role.INSTITUTE_ADMIN,
        institute=institute,
        first_name=admin_first_name.strip(),
        last_name=admin_last_name.strip(),
        timezone=institute.timezone,
    )
    issued = create_set_password_token(admin_user)
    set_password_path = reverse("accounts:set_password", kwargs={"token": issued.key})
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
    timezone: str,
    currency_code: str,
) -> Institute:
    institute.name = name.strip()
    institute.plan = plan
    institute.timezone = timezone.strip()
    institute.currency_code = currency_code
    institute.currency_symbol = CURRENCY_SYMBOLS.get(currency_code, "")
    institute.full_clean()
    institute.save()
    return institute


def set_institute_active(institute: Institute, *, is_active: bool) -> Institute:
    """Activate or deactivate; users of an inactive institute cannot sign in."""
    institute.is_active = is_active
    institute.save(update_fields=["is_active"])
    return institute


def list_institutes(search: str = "") -> QuerySet[Institute]:
    """All institutes with user counts; Institute is global, not tenant-scoped."""
    queryset = Institute.objects.select_related("plan").annotate(
        user_count=Count("users")
    )
    search = search.strip()
    if search:
        queryset = queryset.filter(Q(name__icontains=search))
    return queryset.order_by("name")


def first_institute_admin(institute: Institute) -> User | None:
    """The oldest active institute admin, who gets a new sign-in link (M2)."""
    return (
        User.objects.filter(
            institute=institute, role=Role.INSTITUTE_ADMIN, is_active=True
        )
        .order_by("pk")
        .first()
    )
