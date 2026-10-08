"""Demo data (dev only): Demo Institute on Premium, sign-ins and SPEC 10 people."""

from __future__ import annotations

import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError, CommandParser

from apps.accounts.models import User
from apps.core.features import PLAN_CODE_PREMIUM
from apps.core.roles import Role
from apps.institutes.models import Institute, Plan
from apps.people.demo import reset_people, seed_people

DEMO_INSTITUTE_NAME = "Demo Institute"
DEMO_SUPER_ADMIN_EMAIL = "demo-super@example.com"
# Teacher, student and guardian sign-ins come from apps.people.demo.
DEMO_INSTITUTE_USERS: tuple[tuple[str, str], ...] = (
    ("demo-admin@example.com", Role.INSTITUTE_ADMIN),
    ("demo-sub@example.com", Role.SUB_ADMIN),
)
PASSWORD_ENV_VAR = "SEED_DEMO_PASSWORD"


class Command(BaseCommand):
    help = "Seed demo data (dev only; needs DEBUG and SEED_DEMO_PASSWORD)."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete the demo data and users and deactivate Demo Institute.",
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
        seed_people(institute, password)
        self.stdout.write(self.style.SUCCESS("Demo data ready."))

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
        deleted = 0
        institute = Institute.objects.filter(name=DEMO_INSTITUTE_NAME).first()
        if institute is not None:
            deleted += reset_people(institute)
            deleted += User.objects.filter(institute=institute).delete()[0]
        deleted += User.objects.filter(email=DEMO_SUPER_ADMIN_EMAIL).delete()[0]
        Institute.objects.filter(name=DEMO_INSTITUTE_NAME).update(is_active=False)
        self.stdout.write(self.style.SUCCESS(f"Demo data reset ({deleted} rows)."))
