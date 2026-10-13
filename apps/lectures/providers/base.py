"""The interface every meeting provider follows (ARCHITECTURE section 7)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from apps.lectures.models import Lecture


class MeetingProvider(Protocol):
    def create_meeting(self, lecture: Lecture, link: str) -> str:
        """Return the link students join with."""

    def cancel_meeting(self, lecture: Lecture) -> None:
        """Close the meeting at the provider, if it has one."""

    def get_participants(self, lecture: Lecture) -> list[str]:
        """Who joined; used for automatic attendance (later providers)."""
