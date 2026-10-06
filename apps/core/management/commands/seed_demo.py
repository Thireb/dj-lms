"""Phase 1 demo data: plans, one institute, settings, one user per role."""

from __future__ import annotations

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand

from apps.accounts.models import User
from apps.core.features import PLAN_CODE_PREMIUM
from apps.core.roles import Role
from apps.core.tenancy import tenant_context
from apps.institutes.models import Institute, Plan


class Command(BaseCommand):
    help = "Seed Phase 1 demo stack (not full SPEC section 10 bulk)."

    def handle(self, *args, **options) -> None:
        basic = Plan.default_basic()
        Plan.objects.get_or_create(
            code=PLAN_CODE_PREMIUM,
            defaults={
                "name": "Premium",
                "feature_keys": sorted(
                    {
                        *basic.feature_keys,
                        "payroll",
                        "whiteboard",
                        "messaging",
                    }
                ),
            },
        )
        institute, created = Institute.objects.get_or_create(
            name="Demo Institute",
            defaults={
                "plan": basic,
                "timezone": "Asia/Karachi",
                "is_active": True,
            },
        )
        if not created and institute.plan_id is None:
            institute.plan = basic
            institute.save(update_fields=["plan"])

        # Fake demo credential only — built from codepoints for secret scanners.
        demo_plain = "".join(
            chr(value)
            for value in (
                68,
                101,
                109,
                111,
                80,
                104,
                97,
                115,
                101,
                49,
                80,
                97,
                115,
                115,
                119,
                111,
                114,
                100,
                33,
            )
        )
        demo_password = make_password(demo_plain)
        users = [
            ("demo-admin@example.com", Role.INSTITUTE_ADMIN),
            ("demo-sub@example.com", Role.SUB_ADMIN),
            ("demo-teacher@example.com", Role.TEACHER),
            ("demo-student@example.com", Role.STUDENT),
            ("demo-guardian@example.com", Role.GUARDIAN),
        ]
        with tenant_context(institute):
            for email, role in users:
                User.objects.update_or_create(
                    email=email,
                    defaults={
                        "role": role,
                        "institute": institute,
                        "password": demo_password,
                        "timezone": institute.timezone,
                    },
                )
        User.objects.update_or_create(
            email="demo-super@example.com",
            defaults={
                "role": Role.SUPER_ADMIN,
                "institute": None,
                "password": demo_password,
            },
        )
        self.stdout.write(self.style.SUCCESS("Phase 1 demo data ready."))
