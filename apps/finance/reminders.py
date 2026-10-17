"""The fee reminder job (roadmap 7.4, SPEC 7): "due in 3 days" and
"overdue" notices, and the late fee (owner decision 2026-10-16: added once
to a challan not paid in full by its due date). Each challan is handled
once: the job sets ``due_reminded_on`` and ``overdue_on``, so it can run
every hour."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from django.db import transaction

from apps.core.tenancy import require_tenant_context
from apps.finance import notices
from apps.finance.models import Challan, ChallanStatus
from apps.finance.services import set_status

DUE_SOON_DAYS = 3
OPEN = [ChallanStatus.PENDING, ChallanStatus.PARTIAL]


@dataclass(frozen=True)
class ReminderRun:
    due_soon: int
    overdue: int


def remind_challans(institute: Any, today: date) -> ReminderRun:
    """``today`` is the institute's local date."""
    require_tenant_context(institute)
    open_ = Challan.objects.filter(status__in=OPEN)
    due_soon = open_.filter(
        due_reminded_on__isnull=True,
        due_date__gt=today,
        due_date__lte=today + timedelta(days=DUE_SOON_DAYS),
    )
    sent = sum(_remind_due(pk, today) for pk in due_soon.values_list("pk", flat=True))
    late = open_.filter(overdue_on__isnull=True, due_date__lt=today)
    overdue = sum(
        _mark_overdue(pk, today, institute.settings.late_fee)
        for pk in late.values_list("pk", flat=True)
    )
    if overdue:
        notices.overdue_summary(institute, overdue)
    return ReminderRun(due_soon=sent, overdue=overdue)


def _remind_due(pk: int, today: date) -> int:
    with transaction.atomic():
        challan = _lock_open(pk)
        if challan is None or challan.due_reminded_on is not None:
            return 0
        challan.due_reminded_on = today
        challan.save(update_fields=["due_reminded_on"])
        notices.challan_due(challan)
    return 1


def _mark_overdue(pk: int, today: date, late_fee: Any) -> int:
    with transaction.atomic():
        challan = _lock_open(pk)
        if challan is None or challan.overdue_on is not None:
            return 0
        added = late_fee > 0 and challan.late_fee == 0
        if added:
            challan.late_fee = late_fee
            set_status(challan)
        challan.overdue_on = today
        challan.save(update_fields=["late_fee", "status", "overdue_on"])
        notices.challan_overdue(challan, late_fee_added=added)
    return 1


def _lock_open(pk: int) -> Challan | None:
    """The challan row, locked, while it is still pending or partial (a
    payment between the query and here closes it)."""
    return (
        Challan.objects.select_for_update(of=("self",))
        .select_related("student__user", "institute")
        .filter(pk=pk, status__in=OPEN)
        .first()
    )
