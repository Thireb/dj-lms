"""Shared UI parts added for the lecture pages (roadmap 3.1)."""

from __future__ import annotations

from datetime import time

from apps.ui.components.actions import IconButton, Toast
from apps.ui.components.layout import LinkTabs
from apps.ui.components.nav import FilterBar
from apps.ui.forms.widgets import TimePicker


def test_link_tabs_are_links_with_the_current_one_marked() -> None:
    html = str(
        LinkTabs(
            [
                {"id": "today", "label": "Today", "url": "?show=today"},
                {"id": "past", "label": "Past", "url": "?show=past"},
            ],
            active="past",
            label="Lecture lists",
        )
    )

    assert '<nav class="link-tabs' in html
    assert 'aria-label="Lecture lists"' in html
    assert 'href="?show=today"' in html
    assert 'aria-current="page">Past</a>' in html
    assert html.count("aria-current") == 1
    assert "min-h-10" in html  # 40px tap target


def test_link_tabs_refuse_unsafe_urls() -> None:
    html = str(LinkTabs([{"id": "a", "label": "A", "url": "javascript:alert(1)"}]))

    assert "javascript:" not in html


def test_hidden_filter_is_kept_but_does_not_count_as_a_filter() -> None:
    html = str(FilterBar([{"name": "show", "value": "past", "hidden": True}]))

    assert '<input type="hidden" name="show" value="past" />' in html
    assert ">Clear<" not in html


def test_kept_filter_does_not_count_and_clear_keeps_it() -> None:
    child = {"name": "child", "label": "Child", "value": "7", "kept": True}
    child["options"] = [("7", "Child A"), ("8", "Child B")]
    subject = {"name": "subject", "label": "Subject", "value": "3"}
    subject["options"] = [("", "Any subject"), ("3", "Math")]

    alone = str(FilterBar([child]))
    both = str(FilterBar([child, subject]))

    assert ">Clear<" not in alone
    assert '<a href="?child=7" class="btn btn-ghost">Clear</a>' in both


def test_kept_filter_value_is_encoded_in_the_clear_link() -> None:
    child = {"name": "child", "value": "7&x=<b>", "kept": True, "options": [("", "")]}
    subject = {"name": "q", "value": "a"}

    html = str(FilterBar([child, subject]))

    assert 'href="?child=7%26x%3D%3Cb%3E"' in html


def test_hidden_filter_value_is_escaped() -> None:
    html = str(FilterBar([{"name": "show", "value": '"><b>x', "hidden": True}]))

    assert "<b>x" not in html


def test_icon_button_opens_other_sites_in_a_new_tab() -> None:
    html = str(
        IconButton("video", "Open link", url="https://meet.example.com/a", new_tab=True)
    )
    plain = str(IconButton("square-pen", "Edit", url="/admin/lectures/1/edit/"))

    assert 'target="_blank" rel="noopener noreferrer"' in html
    assert "target=" not in plain


def test_warning_toast_has_its_own_look() -> None:
    html = str(Toast("Morning also has a lecture then.", tone="warning"))

    assert "border-warning/30" in html
    assert "bg-warning-50 text-warning" in html
    assert "#triangle-alert" in html


def test_time_picker_shows_hours_and_minutes() -> None:
    html = TimePicker().render("t", time(15, 0), {"id": "id_t"})

    assert 'value="15:00"' in html
