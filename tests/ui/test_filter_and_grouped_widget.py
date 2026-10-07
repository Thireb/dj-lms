"""FilterBar selects and the GroupedCheckboxes widget."""

from __future__ import annotations

from apps.ui.components.nav import FilterBar
from apps.ui.forms.widgets import GroupedCheckboxes
from django import forms


def test_filter_bar_renders_select_with_selected_value() -> None:
    html = str(
        FilterBar(
            filters=[
                {
                    "name": "status",
                    "label": "Status",
                    "value": "inactive",
                    "options": [("", "Any"), ("active", "Active"), ("inactive", "No")],
                }
            ]
        )
    )

    assert '<select name="status"' in html
    assert '<option value="inactive" selected>No</option>' in html
    assert '<option value="active">Active</option>' in html


def test_filter_bar_escapes_option_labels() -> None:
    html = str(
        FilterBar(filters=[{"name": "b", "label": "B", "options": [("1", "<i>x")]}])
    )

    assert "&lt;i&gt;x" in html


def test_grouped_checkboxes_render_one_fieldset_per_group() -> None:
    class Demo(forms.Form):
        pairs = forms.MultipleChoiceField(
            choices=[("Morning", [("1:1", "Math")]), ("Evening", [("2:1", "Math")])],
            widget=GroupedCheckboxes(),
        )

    html = str(Demo(initial={"pairs": ["2:1"]})["pairs"])

    assert html.count("<fieldset") == 2
    assert ">Morning</legend>" in html
    assert 'value="2:1" id="id_pairs_1_0" checked' in html
    assert 'value="1:1" id="id_pairs_0_0">' in html


def test_grouped_checkboxes_show_empty_text() -> None:
    class Demo(forms.Form):
        pairs = forms.MultipleChoiceField(
            choices=[], widget=GroupedCheckboxes(empty_text="Add batches first.")
        )

    assert "Add batches first." in str(Demo()["pairs"])
