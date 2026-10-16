"""Messaging components (roadmap 6.3): the folder table and the thread."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from django.utils.text import Truncator

from apps.lectures.times import local_date, local_time
from apps.messaging.models import Message
from apps.messaging.services import ThreadRow
from apps.ui.components import Badge, Column, ConfirmDialog, DataTable
from apps.ui.components.actions import IconButton
from apps.ui.components.block_stack import BlockStack, ButtonRow

PREVIEW = 70  # characters of the last message in the list
MONITOR_NOTICE = "Institute admins can read all messages."  # owner decision


def when(value) -> str:
    return f"{local_date(value)}, {local_time(value)}"


def person(user: Any) -> str:
    return user.get_full_name() or user.email


class MessageTable(DataTable):
    """One folder: who, the subject (New while unread), the last message
    and its time. ``open_url`` builds the thread link."""

    empty_title = "No messages here."

    def __init__(self, rows: list[ThreadRow], open_url, **props):
        self.open_url = open_url
        super().__init__(rows=rows, **props)

    @property
    def columns(self) -> list[Column]:  # type: ignore[override]
        return [
            Column("people", "With", lambda row: row.people or "-"),
            Column("subject", "Subject", self.subject),
            Column(
                "preview",
                "Last message",
                lambda row: Truncator(row.last_body).chars(PREVIEW),
            ),
            Column("when", "Date", lambda row: when(row.thread.last_message_at)),
            Column("actions", "", self.open_button),
        ]

    def subject(self, row: ThreadRow) -> Any:
        if not row.unread:
            return row.thread.subject
        return BlockStack(blocks=[Badge("New", tone="info"), row.thread.subject])

    def open_button(self, row: ThreadRow) -> IconButton:
        label = f"Open {row.thread.subject}"
        return IconButton("eye", label, url=self.open_url(row.thread))


def message_rows(messages: list[Message], user: Any) -> list[Any]:
    """Rows for ``MessageList``."""
    return [
        SimpleNamespace(
            author="You" if message.sender_id == user.pk else person(message.sender),
            when=when(message.created_at),
            body=message.body,
            mine=message.sender_id == user.pk,
        )
        for message in messages
    ]


class DraftTable(DataTable):
    """Drafts: To, Subject, Saved; Open (back to the compose page) and Delete."""

    empty_title = "No drafts."

    def __init__(self, rows, open_url, delete_url, **props):
        self.open_url, self.delete_url = open_url, delete_url
        super().__init__(rows=rows, **props)

    @property
    def columns(self) -> list[Column]:  # type: ignore[override]
        return [
            Column("to", "To", lambda d: person(d.recipient) if d.recipient else "-"),
            Column("subject", "Subject", lambda d: d.subject or "(No subject)"),
            Column("when", "Saved", lambda d: when(d.updated_at)),
            Column("actions", "", self.buttons),
        ]

    def buttons(self, draft) -> Any:
        return ButtonRow(
            items=[
                IconButton("square-pen", "Open draft", url=self.open_url(draft)),
                ConfirmDialog(
                    "Delete this draft? This cannot be undone.",
                    "Delete draft",
                    url=self.delete_url(draft),
                    trigger_label="Delete",
                    dismiss_label="Keep draft",
                ),
            ]
        )


class MonitorTable(DataTable):
    """Message Monitor (SPEC 3): Date, From, To, Subject, Last message."""

    empty_title = "No messages match."

    def __init__(self, rows, open_url, **props):
        self.open_url = open_url
        super().__init__(rows=rows, **props)

    @property
    def columns(self) -> list[Column]:  # type: ignore[override]
        return [
            Column("when", "Date", lambda row: when(row.thread.last_message_at)),
            Column("from", "From", lambda row: row.sender),
            Column("to", "To", lambda row: row.to),
            Column("subject", "Subject", lambda row: row.thread.subject),
            Column(
                "preview",
                "Last message",
                lambda row: Truncator(row.last_body).chars(PREVIEW),
            ),
            Column("actions", "", self.open_button),
        ]

    def open_button(self, row) -> IconButton:
        url = self.open_url(row.thread)
        return IconButton("eye", f"Open {row.thread.subject}", url=url)


class BroadcastTable(DataTable):
    """Sent broadcasts: Date, Sent to, Subject, People."""

    empty_title = "No broadcasts yet."

    @property
    def columns(self) -> list[Column]:  # type: ignore[override]
        return [
            Column("when", "Date", lambda b: when(b.created_at)),
            Column("audience", "Sent to", self.audience),
            Column("subject", "Subject", lambda b: b.subject),
            Column("recipients", "People", lambda b: str(b.recipients)),
        ]

    def audience(self, broadcast) -> str:
        label = broadcast.get_audience_display()
        return f"{label}: {broadcast.batch.name}" if broadcast.batch else label
