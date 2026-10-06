from __future__ import annotations

from django.db import models

from apps.core.features import (
    BASIC_PLAN_FEATURES,
    PLAN_CODE_BASIC,
)
from apps.core.models.tenant import TenantModel
from apps.institutes.constants import CURRENCY_SYMBOLS


class Plan(models.Model):
    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=64)
    feature_keys = models.JSONField(default=list)

    class Meta:
        ordering = ["code"]

    def __str__(self) -> str:
        return self.name

    @classmethod
    def default_basic(cls) -> Plan:
        plan, _ = cls.objects.get_or_create(
            code=PLAN_CODE_BASIC,
            defaults={
                "name": "Basic",
                "feature_keys": sorted(BASIC_PLAN_FEATURES),
            },
        )
        return plan


class Institute(models.Model):
    name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    timezone = models.CharField(max_length=63, default="Asia/Karachi")
    plan = models.ForeignKey(
        Plan,
        on_delete=models.PROTECT,
        related_name="institutes",
    )
    address = models.TextField(blank=True, default="")
    phone = models.CharField(max_length=32, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    currency_code = models.CharField(max_length=3, default="PKR")
    currency_symbol = models.CharField(max_length=8, default="Rs")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    @property
    def features(self) -> frozenset[str]:
        if self.plan_id is None:
            return frozenset()
        keys = self.plan.feature_keys or []
        return frozenset(str(key) for key in keys)

    def save(self, *args, **kwargs) -> None:
        if not self.currency_symbol and self.currency_code:
            self.currency_symbol = CURRENCY_SYMBOLS.get(self.currency_code, "")
        super().save(*args, **kwargs)


class InstituteSettings(TenantModel):
    institute = models.OneToOneField(
        "institutes.Institute",
        on_delete=models.PROTECT,
        related_name="settings",
    )
    join_window_minutes = models.PositiveSmallIntegerField(default=10)
    fee_due_day = models.PositiveSmallIntegerField(default=10)
    grace_days_after_due = models.PositiveSmallIntegerField(default=5)
    auto_block_defaulters = models.BooleanField(default=False)
    auto_approve_guardian_receipts = models.BooleanField(default=False)
    require_admin_approval_homework = models.BooleanField(default=False)
    require_admin_approval_lesson_plans = models.BooleanField(default=False)
    require_admin_approval_daily_reports = models.BooleanField(default=True)
    teacher_leave_days_per_year = models.PositiveSmallIntegerField(default=12)
    attendance_present_min_percent = models.PositiveSmallIntegerField(default=75)
    attendance_partial_min_percent = models.PositiveSmallIntegerField(default=25)
    attendance_late_after_minutes = models.PositiveSmallIntegerField(default=10)
    lock_course_document_downloads = models.BooleanField(default=False)
    recurring_lecture_horizon_weeks = models.PositiveSmallIntegerField(default=8)

    class Meta:
        verbose_name_plural = "Institute settings"

    def __str__(self) -> str:
        return f"Settings for {self.institute.name}"
