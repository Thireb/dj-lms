"""R4b: tables, filters, pagination and the form layout (Lexicon redesign)."""

from __future__ import annotations

import re

from apps.ui.components.actions import IconButton
from apps.ui.components.block_stack import ButtonRow
from apps.ui.components.data import Column, DataTable, PersonCell
from apps.ui.components.forms import PortalPostForm
from apps.ui.components.nav import FilterBar, Pagination
from apps.ui.forms.base import BaseForm, Layout, Section
from django import forms
from django.core.paginator import Paginator


def test_table_cells_carry_their_column_label_for_phone_cards() -> None:
    table = DataTable(
        [{"name": "Zoya", "phone": "0300-0000000"}],
        columns=[Column("name", "Student"), Column("phone", "Phone")],
    )
    html = str(table)
    assert 'class="px-4 py-3 align-middle cell-phone" data-label="Phone"' in html
    assert 'data-label="Student"' in html


def test_empty_table_keeps_its_message() -> None:
    html = str(DataTable([], columns=[Column("name", "Name")], empty_title="None."))
    assert "None." in html


def test_phone_table_rules_sit_outside_the_component_layer() -> None:
    """Inside @layer the desktop padding utilities on cells win on phones."""
    css = open("static/css/src/input.css").read()
    layer = css[css.index("@layer components") :]
    assert ".data-table td::before" in css
    assert css.index("Tables become cards on phones") > css.index("@layer components")
    assert "Tables become cards on phones" not in layer.split("\n}\n", 1)[0]


def test_person_cell_shows_avatar_name_and_detail() -> None:
    html = str(PersonCell("Zoya Placeholder", detail="STU-001"))
    assert "person-cell" in html
    assert ">ZP<" in html
    assert ">Zoya Placeholder<" in html
    assert ">STU-001<" in html


def test_icon_button_has_a_label_for_screen_readers() -> None:
    link = str(IconButton("square-pen", "Edit Zoya", url="/edit/"))
    assert '<a href="/edit/"' in link
    assert 'aria-label="Edit Zoya"' in link
    button = str(IconButton("x", "Close"))
    assert '<button type="button"' in button


def test_icon_button_escapes_its_label() -> None:
    html = str(IconButton("x", '"><script>'))
    assert "<script>" not in html


def test_button_row_renders_items_side_by_side() -> None:
    html = str(ButtonRow([IconButton("x", "One"), IconButton("x", "Two")]))
    assert "button-row flex flex-wrap" in html
    assert html.index("One") < html.index("Two")


def test_pagination_shows_range_and_page_numbers() -> None:
    page = Paginator(list(range(250)), 25).get_page(5)
    html = str(Pagination(page, query="q=a"))
    assert "Showing 101 to 125 of 250" in html
    assert 'aria-current="page" aria-label="Page 5 of 10"' in html
    assert 'href="?q=a&page=4" aria-label="Page 4"' in html
    assert "…" in html  # long ranges are elided
    assert 'aria-label="Next page"' in html


def test_pagination_hides_numbers_on_one_page() -> None:
    html = str(Pagination(Paginator([1, 2], 25).get_page(1)))
    assert "Showing 1 to 2 of 2" in html
    assert "<ul" not in html


def test_filter_bar_offers_clear_only_when_a_filter_is_set() -> None:
    plain = str(FilterBar(filters=[{"name": "q", "label": "Search"}]))
    assert "Clear" not in plain
    used = str(FilterBar(filters=[{"name": "q", "label": "Search", "value": "a"}]))
    assert 'href="?"' in used and ">Clear<" in used


class _SectionForm(BaseForm):
    name = forms.CharField()
    city = forms.CharField()

    def get_layout(self):
        return Layout(
            Section(
                "Contact", "name", "city", description="How we reach you.", columns=2
            )
        )


def _render(form) -> str:
    from crispy_forms.utils import render_crispy_form

    return render_crispy_form(form)


def test_section_has_title_description_and_labelled_fieldset() -> None:
    html = _render(_SectionForm())
    assert '<h3 id="section-contact"' in html
    assert "How we reach you." in html
    assert 'aria-labelledby="section-contact"' in html
    assert re.search(r"<fieldset[^>]*md:grid-cols-2", html)


def test_section_without_title_is_one_column() -> None:
    class Plain(_SectionForm):
        def get_layout(self):
            return Layout(Section(None, "name"))

    html = _render(Plain())
    assert "<h3" not in html
    assert "aria-labelledby" not in html
    assert "md:grid-cols-[15rem" not in html


def test_portal_form_is_framed_unless_asked_not_to() -> None:
    framed = str(PortalPostForm(action="/save/", body="body"))
    assert "rounded-[18px] border border-border bg-surface" in framed
    bare = str(PortalPostForm(action="/save/", body="body", framed=False))
    assert "rounded-[18px]" not in bare
