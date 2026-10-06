# Generated manually for roadmap 1.2

from __future__ import annotations

import django.db.models.deletion
from django.db import migrations, models

BASIC_FEATURES = [
    "fees",
    "leave",
    "homework",
    "lesson_plans",
    "time_zone_lectures",
]

PREMIUM_FEATURES = [
    "fees",
    "payroll",
    "whiteboard",
    "leave",
    "homework",
    "lesson_plans",
    "messaging",
    "time_zone_lectures",
]


def seed_plans_and_assign_basic(apps, schema_editor) -> None:
    Plan = apps.get_model("institutes", "Plan")
    Institute = apps.get_model("institutes", "Institute")
    basic, _ = Plan.objects.get_or_create(
        code="basic",
        defaults={"name": "Basic", "feature_keys": BASIC_FEATURES},
    )
    Plan.objects.get_or_create(
        code="premium",
        defaults={"name": "Premium", "feature_keys": PREMIUM_FEATURES},
    )
    Institute.objects.filter(plan__isnull=True).update(plan=basic)


def backfill_institute_settings(apps, schema_editor) -> None:
    Institute = apps.get_model("institutes", "Institute")
    InstituteSettings = apps.get_model("institutes", "InstituteSettings")
    for institute in Institute.objects.all():
        InstituteSettings.objects.get_or_create(institute=institute)


class Migration(migrations.Migration):
    dependencies = [
        ("institutes", "0002_institute_is_active"),
    ]

    operations = [
        migrations.CreateModel(
            name="Plan",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("code", models.CharField(max_length=32, unique=True)),
                ("name", models.CharField(max_length=64)),
                ("feature_keys", models.JSONField(default=list)),
            ],
            options={
                "ordering": ["code"],
            },
        ),
        migrations.AddField(
            model_name="institute",
            name="address",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="institute",
            name="currency_code",
            field=models.CharField(default="PKR", max_length=3),
        ),
        migrations.AddField(
            model_name="institute",
            name="currency_symbol",
            field=models.CharField(default="Rs", max_length=8),
        ),
        migrations.AddField(
            model_name="institute",
            name="email",
            field=models.EmailField(blank=True, default="", max_length=254),
        ),
        migrations.AddField(
            model_name="institute",
            name="phone",
            field=models.CharField(blank=True, default="", max_length=32),
        ),
        migrations.AddField(
            model_name="institute",
            name="plan",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="institutes",
                to="institutes.plan",
            ),
        ),
        migrations.RunPython(seed_plans_and_assign_basic, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="institute",
            name="plan",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="institutes",
                to="institutes.plan",
            ),
        ),
        migrations.CreateModel(
            name="InstituteSettings",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("join_window_minutes", models.PositiveSmallIntegerField(default=10)),
                ("fee_due_day", models.PositiveSmallIntegerField(default=10)),
                ("grace_days_after_due", models.PositiveSmallIntegerField(default=5)),
                ("auto_block_defaulters", models.BooleanField(default=False)),
                (
                    "auto_approve_guardian_receipts",
                    models.BooleanField(default=False),
                ),
                (
                    "require_admin_approval_homework",
                    models.BooleanField(default=False),
                ),
                (
                    "require_admin_approval_lesson_plans",
                    models.BooleanField(default=False),
                ),
                (
                    "require_admin_approval_daily_reports",
                    models.BooleanField(default=True),
                ),
                (
                    "teacher_leave_days_per_year",
                    models.PositiveSmallIntegerField(default=12),
                ),
                (
                    "attendance_present_min_percent",
                    models.PositiveSmallIntegerField(default=75),
                ),
                (
                    "attendance_partial_min_percent",
                    models.PositiveSmallIntegerField(default=25),
                ),
                (
                    "attendance_late_after_minutes",
                    models.PositiveSmallIntegerField(default=10),
                ),
                (
                    "lock_course_document_downloads",
                    models.BooleanField(default=False),
                ),
                (
                    "recurring_lecture_horizon_weeks",
                    models.PositiveSmallIntegerField(default=8),
                ),
                (
                    "institute",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="settings",
                        to="institutes.institute",
                    ),
                ),
            ],
            options={
                "verbose_name_plural": "Institute settings",
            },
        ),
        migrations.RunPython(backfill_institute_settings, migrations.RunPython.noop),
    ]
