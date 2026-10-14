"""Demo attendance for seed_demo: marks on the first two finished demo
lectures. The newest finished lecture stays unmarked, so the demo teacher
sees "Take attendance".

Demo people are made at seed time, after last week's demo lectures. Their
enrolments are dated 30 days back, so those lectures have a roster (the
roster counts enrolments made before a lecture ended).
"""

from __future__ import annotations

from datetime import timedelta
from itertools import cycle

from django.utils import timezone

from apps.academics.models import StudentBatchSubject
from apps.attendance.models import Attendance, AttendanceStatus
from apps.attendance.services import roster, save_marks
from apps.core.tenancy import tenant_context
from apps.institutes.models import Institute
from apps.lectures.models import Lecture, LectureStatus
from apps.people.demo import DEMO_TEACHER_EMAIL

ENROLLED_DAYS_AGO = 30
MARKED_LECTURES = 2
PATTERN = (
    AttendanceStatus.PRESENT,
    AttendanceStatus.PRESENT,
    AttendanceStatus.LATE,
    AttendanceStatus.PRESENT,
    AttendanceStatus.PARTIAL,
    AttendanceStatus.ABSENT,
)


def seed_attendance(institute: Institute) -> None:
    """Mark the demo lectures once (a second run adds nothing)."""
    with tenant_context(institute):
        if Attendance.objects.exists():
            return
        enrolled = timezone.now() - timedelta(days=ENROLLED_DAYS_AGO)
        StudentBatchSubject.objects.filter(created_at__gt=enrolled).update(
            created_at=enrolled
        )
        lectures = Lecture.objects.filter(
            teacher__user__email=DEMO_TEACHER_EMAIL, status=LectureStatus.FINISHED
        ).order_by("starts_at")[:MARKED_LECTURES]
        statuses = cycle(PATTERN)
        for lecture in lectures:
            marks = {entry.student.pk: next(statuses) for entry in roster(lecture)}
            save_marks(lecture, marks, marked_by=lecture.teacher.user)


def reset_attendance(institute: Institute) -> int:
    """Delete the institute's marks (before its lectures and students).

    Uses ``unscoped`` on purpose: a management command, one institute.
    """
    # unscoped: seed_demo --reset, limited to the demo institute.
    deleted, _ = Attendance.unscoped.filter(institute=institute).delete()
    return deleted
