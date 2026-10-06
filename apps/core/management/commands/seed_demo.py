"""Phase 1 demo data: Demo Institute on Premium and one user per role (dev only)."""

from __future__ import annotations

import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError, CommandParser

from apps.accounts.models import User
from apps.core.features import PLAN_CODE_PREMIUM
from apps.core.roles import Role
from apps.institutes.models import Institute, Plan

DEMO_INSTITUTE_NAME = "Demo Institute"
DEMO_SUPER_ADMIN_EMAIL = "demo-super@example.com"
DEMO_INSTITUTE_USERS: tuple[tuple[str, str], ...] = (
    ("demo-admin@example.com", Role.INSTITUTE_ADMIN),
    ("demo-sub@example.com", Role.SUB_ADMIN),
    ("demo-teacher@example.com", Role.TEACHER),
    ("demo-student@example.com", Role.STUDENT),
    ("demo-guardian@example.com", Role.GUARDIAN),
)
PASSWORD_ENV_VAR = "SEED_DEMO_PASSWORD"


class Command(BaseCommand):
    help = "Seed Phase 1 demo data (dev only; needs DEBUG and SEED_DEMO_PASSWORD)."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete the demo users and deactivate Demo Institute.",
        )

    def handle(self, *args, **options) -> None:
        if not settings.DEBUG:
            raise CommandError("seed_demo runs only when DEBUG is True.")
        if options["reset"]:
            self._reset()
            return
        password = os.environ.get(PASSWORD_ENV_VAR, "")
        if not password:
            raise CommandError(f"Set {PASSWORD_ENV_VAR} (see .env.example).")
        institute = self._demo_institute()
        for email, role in DEMO_INSTITUTE_USERS:
            self._upsert_user(email, role, password, institute=institute)
        self._upsert_user(DEMO_SUPER_ADMIN_EMAIL, Role.SUPER_ADMIN, password)
        self.stdout.write(self.style.SUCCESS("Phase 1 demo data ready."))

    def _demo_institute(self) -> Institute:
        institute, _ = Institute.objects.update_or_create(
            name=DEMO_INSTITUTE_NAME,
            defaults={
                "plan": Plan.objects.get(code=PLAN_CODE_PREMIUM),
                "timezone": "Asia/Karachi",
                "is_active": True,
            },
        )
        return institute

    def _upsert_user(
        self,
        email: str,
        role: str,
        password: str,
        *,
        institute: Institute | None = None,
    ) -> None:
        user = User.objects.filter(email=email).first() or User(email=email)
        user.role = role
        user.institute = institute
        user.timezone = institute.timezone if institute else ""
        user.is_active = True
        user.set_password(password)
        user.save()

    def _reset(self) -> None:
        emails = [email for email, _ in DEMO_INSTITUTE_USERS]
        emails.append(DEMO_SUPER_ADMIN_EMAIL)
        deleted, _ = User.objects.filter(email__in=emails).delete()
        Institute.objects.filter(name=DEMO_INSTITUTE_NAME).update(is_active=False)
        self.stdout.write(self.style.SUCCESS(f"Demo data reset ({deleted} rows)."))
