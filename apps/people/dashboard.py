"""Service layer for the admin main dashboard (roadmap 2.4, SPEC 8).

Only what exists now: students, teachers and running batches. Lectures
today (Phase 3), the fee strip and waiting receipts (Phase 7) and pending
approvals (Phase 9) are added by those phases.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.db.models import Count, Q

from apps.academics.models import Batch
from apps.people.models import ProfileStatus, StudentProfile, TeacherProfile
from apps.people.services import list_students, list_teachers

RECENT_COUNT = 5


@dataclass(frozen=True)
class PeopleCounts:
    total: int
    active: int

    @property
    def inactive(self) -> int:
        return self.total - self.active

    @property
    def active_percent(self) -> int:
        return round(100 * self.active / self.total) if self.total else 0


@dataclass(frozen=True)
class AdminDashboard:
    students: PeopleCounts
    teachers: PeopleCounts
    batches_total: int
    batches_running: int
    recent_students: list[StudentProfile]
    recent_teachers: list[TeacherProfile]


def _counts(model: type[StudentProfile] | type[TeacherProfile], user) -> PeopleCounts:
    totals = model.objects.for_user(user).aggregate(
        total=Count("pk"), active=Count("pk", filter=Q(status=ProfileStatus.ACTIVE))
    )
    return PeopleCounts(total=totals["total"], active=totals["active"])


def admin_dashboard(user: object) -> AdminDashboard:
    """Counts and recent rows the user may see (``for_user`` scopes all)."""
    batches = Batch.objects.for_user(user)
    running = batches.filter(
        student_links__student__status=ProfileStatus.ACTIVE
    ).distinct()
    return AdminDashboard(
        students=_counts(StudentProfile, user),
        teachers=_counts(TeacherProfile, user),
        batches_total=batches.count(),
        batches_running=running.count(),
        recent_students=list(list_students(user)[:RECENT_COUNT]),
        recent_teachers=list(list_teachers(user)[:RECENT_COUNT]),
    )
