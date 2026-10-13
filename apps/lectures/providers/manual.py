"""Manual link (the teacher pastes any link) and in person (no link)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apps.lectures.models import Lecture


class ManualLinkProvider:
    """The pasted link is the meeting. Nothing to cancel, no auto attendance."""

    def create_meeting(self, lecture: Lecture, link: str) -> str:
        return link.strip()

    def cancel_meeting(self, lecture: Lecture) -> None:
        return None

    def get_participants(self, lecture: Lecture) -> list[str]:
        return []


class NoMeetingProvider(ManualLinkProvider):
    """In-person lectures have no link."""

    def create_meeting(self, lecture: Lecture, link: str) -> str:
        return ""
