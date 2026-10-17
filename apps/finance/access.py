"""The automatic defaulter rule (roadmap 7.6, SPEC 6.2). With the setting
"Auto-block defaulters" on, a nightly run blocks every defaulter who is not
exempt, and unblocks the students it blocked once nothing of theirs is
overdue beyond grace (or they became exempt). It never undoes a manual
block; a manual unblock of a defaulter lasts until the next run."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from apps.core.tenancy import require_tenant_context
from apps.finance.models import Challan
from apps.finance.reports import beyond_grace
from apps.people.models import PortalAccessRule, StudentProfile
from apps.people.services import set_portal_blocked


@dataclass(frozen=True)
class AccessRun:
    blocked: int
    unblocked: int


def apply_defaulter_rule(institute: Any, today: date) -> AccessRun:
    require_tenant_context(institute)
    if not institute.settings.auto_block_defaulters:
        return AccessRun(blocked=0, unblocked=0)
    owing = set(
        beyond_grace(Challan.objects.all(), institute, today).values_list(
            "student_id", flat=True
        )
    )
    rules = {rule.student_id: rule for rule in PortalAccessRule.objects.all()}
    to_block = [
        pk
        for pk in owing
        if pk not in rules or not (rules[pk].blocked or rules[pk].exempt)
    ]
    to_open = [
        pk
        for pk, rule in rules.items()
        if rule.auto_blocked and (pk not in owing or rule.exempt)
    ]
    students = StudentProfile.objects.select_related("user").in_bulk(to_block + to_open)
    for pk in to_block:
        set_portal_blocked(students[pk], blocked=True, by_rule=True)
    for pk in to_open:
        set_portal_blocked(students[pk], blocked=False)
    return AccessRun(blocked=len(to_block), unblocked=len(to_open))
