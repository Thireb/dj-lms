"""Nested components get the request, so forms inside lists carry CSRF."""

from __future__ import annotations

from apps.ui.components.actions import ConfirmDialog
from apps.ui.components.block_stack import BlockStack
from apps.ui.components.data import Column, DataTable
from apps.ui.components.layout import PageHeader, SectionCard
from apps.ui.components.page_layouts import DetailPageBody, ListPageBody
from django.middleware.csrf import get_token
from django.test import RequestFactory

TOKEN_FIELD = 'name="csrfmiddlewaretoken"'


def _request():
    request = RequestFactory().get("/admin/batches/")
    get_token(request)
    return request


def _dialog() -> ConfirmDialog:
    return ConfirmDialog("Deactivate Morning?", "Deactivate", url="/admin/x/")


def test_data_table_cell_gets_request() -> None:
    table = DataTable(rows=[{}], columns=[Column("a", "A", lambda row: _dialog())])

    assert TOKEN_FIELD in table.render(request=_request())
    assert TOKEN_FIELD not in str(table)


def test_block_stack_block_gets_request() -> None:
    stack = BlockStack(blocks=["Plain <b>text</b>", _dialog()])
    html = stack.render(request=_request())

    assert TOKEN_FIELD in html
    assert "Plain &lt;b&gt;text&lt;/b&gt;" in html


def test_list_page_body_passes_request_to_table() -> None:
    table = DataTable(
        rows=[{}],
        columns=[Column("a", "A", lambda row: BlockStack(blocks=[_dialog()]))],
    )
    body = ListPageBody(header=PageHeader(title="Batches"), table=table)

    assert TOKEN_FIELD in body.render(request=_request())


def test_detail_page_body_passes_request_to_cards() -> None:
    body = DetailPageBody(
        header=PageHeader(title="Upload"),
        primary_cards=[SectionCard(title="Card", body=BlockStack(blocks=[_dialog()]))],
        sidebar_cards=[_dialog()],
    )

    assert body.render(request=_request()).count(TOKEN_FIELD) == 2
