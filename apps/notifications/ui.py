"""Notification components (roadmap 6.1): rows for the bell and the page."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from django.urls import reverse

from apps.lectures.times import local_date, local_time
from apps.notifications.models import Notification
from apps.ui.components import Badge, Column, DataTable, PostButton


def when(value: datetime) -> str:
    """Example: Fri 16 Oct 2026, 3:05 PM PKT."""
    return f"{local_date(value)}, {local_time(value)}"


def open_url(row: Notification) -> str:
    return reverse("notifications:open", kwargs={"pk": row.pk})


@dataclass(frozen=True)
class PanelRow:
    text: str
    when: str
    open_url: str
    is_read: bool


def panel_rows(rows: list[Notification]) -> list[PanelRow]:
    return [
        PanelRow(row.text, when(row.created_at), open_url(row), row.is_read)
        for row in rows
    ]


class NotificationTable(DataTable):
    """The Notifications page: the text, New while unread, the time, and
    Open (marks it read and opens its link)."""

    empty_title = "No notifications yet."

    def __init__(self, rows: list[Notification], **props):
        super().__init__(rows=rows, **props)

    @property
    def columns(self) -> list[Column]:  # type: ignore[override]
        return [
            Column("text", "Notification", lambda row: row.text),
            Column("status", "Status", self.status),
            Column("when", "When", lambda row: when(row.created_at)),
            Column("actions", "", self.open_button),
        ]

    def status(self, row: Notification) -> Badge | str:
        return "" if row.is_read else Badge("New", tone="info")

    def open_button(self, row: Notification) -> PostButton:
        return PostButton("Open", open_url(row), variant="secondary")
