"""Portal home pages for teachers, students and guardians (roadmap R4c).

A welcome band, the "Up next" card with a countdown (roadmap 3.4), and
what exists now: batches and subjects, and a guardian's children.
"""

from __future__ import annotations

from functools import cached_property
from typing import Any

from django.utils import timezone

from apps.attendance.services import lectures_to_mark, student_summaries
from apps.attendance.ui import attendance_value, classes_note
from apps.core.roles import Role
from apps.lectures.services import lectures_today_count, upcoming_lectures
from apps.lectures.ui import lecture_status_badge, lecture_summary, lecture_when
from apps.lectures.views import up_next_body
from apps.people.home import greeting, guardian_home, student_home, teacher_home
from apps.people.ui import profile_status_badge
from apps.people.views import GuardianChildMixin
from apps.ui.brand import initials
from apps.ui.components.block_stack import BlockStack
from apps.ui.components.data import EmptyState, PersonCell, PersonList, StatCard
from apps.ui.components.layout import HeroBanner, SectionCard
from apps.ui.components.lectures import LectureRow
from apps.ui.views.pages import DashboardPage


class PortalHomePage(DashboardPage):
    """Welcome band and the "Up next" card shared by the sidebar portals."""

    title = "Dashboard"
    active_item = "dashboard"
    up_next_title = "Up next"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        self.data = self.load(self.request.user)
        return super().get_context_data(**kwargs)

    def load(self, user: Any) -> Any:
        raise NotImplementedError

    def person_name(self) -> str:
        profile = getattr(self.data, "profile", None)
        return str(profile) if profile else self.request.user.email

    def first_name(self) -> str:
        return self.request.user.first_name or self.person_name()

    def get_subtitle_line(self) -> str:
        return self.request.user.email

    def get_chips(self) -> list[str]:
        return []

    def get_hero(self) -> HeroBanner:
        hello = greeting(timezone.localtime())
        return HeroBanner(
            title=f"{hello}, {self.first_name()}",
            subtitle=self.get_subtitle_line(),
            chips=self.get_chips(),
            initials=initials(self.person_name()),
        )

    def up_next(self) -> SectionCard:
        return SectionCard(
            title=self.up_next_title, icon="video", body=self.up_next_body()
        )

    def up_next_body(self) -> Any:
        return up_next_body(self.request, self.portal, self.get_institute())

    def get_feature(self) -> SectionCard:
        return self.up_next()


UPCOMING_COUNT = 5


def children_in(lecture: Any, children: list[Any]) -> list[str]:
    """Names of the children enrolled in the lecture's batch and one of its
    subjects (the same rule as ``Lecture.objects.for_user``)."""
    subject_ids = {subject.pk for subject in lecture.subjects.all()}
    return [
        str(child)
        for child in children
        if any(
            link.batch_id == lecture.batch_id and link.subject_id in subject_ids
            for link in child.batch_subjects.all()
        )
    ]


def _code_line(code: str, *parts: str) -> str:
    return ", ".join(part for part in (code, *parts) if part)


class TeacherPortalHomePage(PortalHomePage):
    portal = "teacher"
    allowed_roles = [Role.TEACHER]

    def load(self, user: Any) -> Any:
        return teacher_home(user)

    def get_subtitle_line(self) -> str:
        code = self.data.profile.teacher_code if self.data.profile else ""
        return _code_line(code, self.request.user.email)

    def get_chips(self) -> list[str]:
        return self.data.pairs

    def get_stat_cards(self) -> list[Any]:
        data = self.data
        today = lectures_today_count(self.request.user)
        return [
            StatCard(today, "Lectures today", icon="video", tone="lead"),
            StatCard(
                len(lectures_to_mark(self.request.user)),
                "Attendance to take",
                note="Finished lectures with no marks",
                icon="clipboard-check",
            ),
            StatCard(data.student_count, "My students", icon="users"),
            StatCard(data.batch_count, "Batches", icon="layers"),
            StatCard(data.subject_count, "Subjects", icon="book-open"),
        ]


class StudentPortalHomePage(PortalHomePage):
    portal = "student"
    allowed_roles = [Role.STUDENT]

    def load(self, user: Any) -> Any:
        return student_home(user)

    def get_subtitle_line(self) -> str:
        profile = self.data.profile
        if profile is None:
            return self.request.user.email
        label = profile.class_label.name if profile.class_label else ""
        return _code_line(profile.student_code, label)

    def get_chips(self) -> list[str]:
        return self.data.pairs

    def get_stat_cards(self) -> list[Any]:
        profile = self.data.profile
        if profile is None:
            return []
        summary = student_summaries([profile])[profile.pk]
        return [
            StatCard(
                attendance_value(summary.percent),
                "Attendance",
                note=classes_note(summary),
                icon="clipboard-check",
                tone="lead",
            ),
            StatCard(
                lectures_today_count(self.request.user), "Lectures today", icon="video"
            ),
        ]


class GuardianPortalHomePage(GuardianChildMixin, PortalHomePage):
    portal = "guardian"
    allowed_roles = [Role.GUARDIAN]
    section_columns = 2
    up_next_title = "Upcoming classes"

    def load(self, user: Any) -> Any:
        return guardian_home(user)

    @cached_property
    def children(self) -> list[Any]:
        """The switcher reuses the children the home already loaded."""
        return self.data.children

    @cached_property
    def summaries(self) -> dict[int, Any]:
        return student_summaries(self.data.children)

    def up_next_body(self) -> Any:
        lectures = upcoming_lectures(self.request.user, limit=UPCOMING_COUNT)
        if not lectures:
            return EmptyState(
                "No upcoming classes",
                text="Your children's next classes show here.",
                icon="calendar",
                framed=False,
            )
        return BlockStack(blocks=[self.class_row(lecture) for lecture in lectures])

    def class_row(self, lecture: Any) -> LectureRow:
        names = children_in(lecture, self.data.children)
        detail = lecture_summary(lecture)
        if len(self.data.children) > 1:
            detail = " · ".join([", ".join(names), detail])
        return LectureRow(
            lecture.title,
            lecture_when(lecture),
            detail=detail,
            trailing=lecture_status_badge(lecture),
        )

    def child_row(self, child: Any) -> tuple[PersonCell, Any]:
        label = child.class_label.name if child.class_label else ""
        batches = ", ".join(
            sorted({link.batch.name for link in child.batch_subjects.all()})
        )
        percent = attendance_value(self.summaries[child.pk].percent)
        detail = _code_line(
            child.student_code, label, batches, f"Attendance: {percent}"
        )
        return PersonCell(str(child), detail=detail), profile_status_badge(child)

    def get_sections(self) -> list[Any]:
        children = SectionCard(
            title="Your children",
            icon="graduation-cap",
            body=PersonList(
                [self.child_row(child) for child in self.data.children],
                empty_text="No children are linked to this account yet. "
                "Contact the institute office.",
            ),
        )
        return [children, self.up_next()]

    def get_feature(self) -> None:
        return None  # "Upcoming classes" sits next to the children instead
