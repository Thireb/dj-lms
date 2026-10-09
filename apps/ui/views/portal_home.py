"""Portal home pages for teachers, students and guardians (roadmap R4c).

A welcome band, an "Up next" card that waits for lectures (Phase 3), and
what exists now: batches and subjects, and a guardian's children.
"""

from __future__ import annotations

from typing import Any

from django.utils import timezone

from apps.core.roles import Role
from apps.people.home import greeting, guardian_home, student_home, teacher_home
from apps.people.ui import profile_status_badge
from apps.ui.brand import initials
from apps.ui.components.data import EmptyState, PersonCell, PersonList, StatCard
from apps.ui.components.layout import HeroBanner, SectionCard
from apps.ui.views.pages import DashboardPage


class PortalHomePage(DashboardPage):
    """Welcome band and the "Up next" card shared by the sidebar portals."""

    title = "Dashboard"
    active_item = "dashboard"
    up_next_title = "Up next"
    up_next_text = (
        "Your next lecture shows here with a countdown once lectures are scheduled."
    )

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
            title=self.up_next_title,
            icon="video",
            body=EmptyState(
                "No lectures yet",
                text=self.up_next_text,
                icon="calendar",
                framed=False,
            ),
        )

    def get_feature(self) -> SectionCard:
        return self.up_next()


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
        return [
            StatCard(data.student_count, "My students", icon="users", tone="lead"),
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


class GuardianPortalHomePage(PortalHomePage):
    portal = "guardian"
    allowed_roles = [Role.GUARDIAN]
    section_columns = 2
    up_next_title = "Upcoming classes"
    up_next_text = "Your children's next classes show here once lectures are scheduled."

    def load(self, user: Any) -> Any:
        return guardian_home(user)

    def child_row(self, child: Any) -> tuple[PersonCell, Any]:
        label = child.class_label.name if child.class_label else ""
        batches = ", ".join(
            sorted({link.batch.name for link in child.batch_subjects.all()})
        )
        detail = _code_line(child.student_code, label, batches)
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
