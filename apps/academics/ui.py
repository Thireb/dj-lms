"""Table for the class, batch and subject lists (SPEC section 3)."""

from __future__ import annotations

from typing import Any

from django.urls import reverse

from apps.academics.models import NameList
from apps.ui.components.actions import Button, ConfirmDialog
from apps.ui.components.block_stack import BlockStack
from apps.ui.components.data import Badge, Column, DataTable


def status_badge(row: NameList) -> Badge:
    if row.is_active:
        return Badge("Active", tone="success")
    return Badge("Inactive", tone="danger")


def status_dialog(row: NameList, url_prefix: str) -> ConfirmDialog:
    url = reverse(f"admin:{url_prefix}_status", kwargs={"pk": row.pk})
    if row.is_active:
        return ConfirmDialog(
            f"Deactivate {row.name}? It cannot be added to new students or teachers.",
            "Deactivate",
            url=url,
            fields=[("action", "deactivate")],
        )
    return ConfirmDialog(
        f"Activate {row.name}? It can be added to students and teachers again.",
        "Activate",
        url=url,
        variant="primary",
        fields=[("action", "activate")],
    )


class NameListTable(DataTable):
    """Name, Students count, Status, and the Edit and status actions."""

    def __init__(self, rows: list[Any], *, url_prefix: str, empty_title: str):
        self.url_prefix = url_prefix
        super().__init__(rows=rows, empty_title=empty_title)

    @property
    def columns(self) -> list[Column]:  # type: ignore[override]
        return [
            Column("name", "Name"),
            Column("student_count", "Students"),
            Column("status", "Status", status_badge),
            Column("actions", "", self.row_actions_for),
        ]

    def row_actions_for(self, row: NameList) -> BlockStack:
        edit_url = reverse(f"admin:{self.url_prefix}_edit", kwargs={"pk": row.pk})
        return BlockStack(
            blocks=[
                Button("Edit", url=edit_url, variant="secondary"),
                status_dialog(row, self.url_prefix),
            ]
        )
