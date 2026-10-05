"""Thread-safe current institute context for tenant scoping."""

from __future__ import annotations

from contextvars import ContextVar
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apps.institutes.models import Institute

_current_institute: ContextVar[Institute | None] = ContextVar(
    "current_institute",
    default=None,
)


def get_current_institute() -> Institute | None:
    return _current_institute.get()


def set_current_institute(institute: Institute | None) -> None:
    _current_institute.set(institute)


def clear_current_institute() -> None:
    _current_institute.set(None)
