"""Thread-safe current institute context for tenant scoping."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token
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


@contextmanager
def tenant_context(institute: Institute | None) -> Iterator[None]:
    """Set the current institute for the duration of the block (Celery, commands)."""
    token: Token[Institute | None] = _current_institute.set(institute)
    try:
        yield
    finally:
        _current_institute.reset(token)
