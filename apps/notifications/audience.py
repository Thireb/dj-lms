"""Who gets a class notification (roadmap 6.2, SPEC 7): the active students
of a batch and its subjects, and their guardians. A guardian's text starts
with the child's name (several children: one notification naming all)."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable
from typing import Any

from apps.academics.models import StudentBatchSubject
from apps.notifications.services import notify
from apps.people.models import GuardianStudentLink, ProfileStatus, StudentProfile

Text = str | Callable[[Any], str]


def without(actor: Any, users: Iterable[Any]) -> list[Any]:
    """The person who made the change does not get a notification about it."""
    actor_id = getattr(actor, "pk", None)
    return [user for user in users if user.pk != actor_id]


def render(text: Text, user: Any) -> str:
    return text(user) if callable(text) else text


def class_students(batch_id: int, subject_ids: Iterable[int]) -> list[StudentProfile]:
    """Active students with an enrolment in the batch and one of the subjects."""
    enrolled = StudentBatchSubject.objects.filter(
        batch_id=batch_id,
        subject_id__in=list(subject_ids),
        student__status=ProfileStatus.ACTIVE,
    ).values("student_id")
    return list(StudentProfile.objects.filter(pk__in=enrolled).select_related("user"))


def send_to_students(
    event: str,
    students: list[StudentProfile],
    text: Text,
    *,
    student_url: str = "",
    guardian_url: str = "",
    actor: Any = None,
    to_students: bool = True,
) -> int:
    """Notify the students, and their guardians when ``guardian_url`` is set.
    ``to_students=False`` sends to the guardians only."""
    made = 0
    if to_students:
        users = without(actor, [student.user for student in students])
        made = notify(users, event, text, student_url)
    if not guardian_url or not students:
        return made
    guardians: dict[int, Any] = {}
    children: dict[int, list[str]] = defaultdict(list)
    links = GuardianStudentLink.objects.filter(student__in=students).select_related(
        "guardian__user", "student__user"
    )
    for link in links:
        user = link.guardian.user
        guardians[user.pk] = user
        children[user.pk].append(str(link.student))

    def guardian_text(user: Any) -> str:
        names = ", ".join(sorted(children[user.pk]))
        return f"For {names}: {render(text, user)}"

    return made + notify(
        without(actor, guardians.values()), event, guardian_text, guardian_url
    )
