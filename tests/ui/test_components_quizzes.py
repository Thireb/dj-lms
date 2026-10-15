"""AttemptTimer, the OptionRadios widget and the FormActions second button
(roadmap 5.3)."""

from __future__ import annotations

from datetime import UTC, datetime

from apps.ui.components.quizzes import AttemptTimer
from apps.ui.forms.layout import FormActions
from apps.ui.forms.widgets import OptionRadios
from django import forms


def test_attempt_timer_renders_deadline_and_form() -> None:
    html = str(
        AttemptTimer(
            datetime(2026, 10, 15, 9, 30, tzinfo=UTC), "attempt-form", label="Ends 2:30"
        )
    )
    assert 'x-data="attemptTimer"' in html
    assert 'data-deadline="2026-10-15T09:30:00+00:00"' in html
    assert 'data-form="attempt-form"' in html
    assert 'role="timer"' in html and "Ends 2:30" in html
    assert 'aria-live="assertive"' in html


def test_attempt_timer_drops_a_bad_deadline_and_escapes() -> None:
    html = str(AttemptTimer("not a date", '"><script>x</script>'))
    assert 'data-deadline=""' in html
    assert "<script>x" not in html


def test_option_radios_rows_wrap_and_escape() -> None:
    field = forms.ChoiceField(
        choices=[("1", "<b>Paris</b>"), ("2", "Rome")],
        widget=OptionRadios(group_label="Question 1"),
    )
    html = field.widget.render("item_1", "2", attrs={"id": "id_item_1"})
    assert 'role="radiogroup"' in html and 'aria-label="Question 1"' in html
    assert "&lt;b&gt;Paris&lt;/b&gt;" in html
    assert 'value="2" id="id_item_1_1" checked' in html
    assert "break-words" in html


def test_form_actions_second_button() -> None:
    html = FormActions(
        "Submit answers", save_name="submit", second=("Save answers", "save")
    ).render(None, {})
    assert 'name="save" value="1" class="btn btn-secondary">Save answers' in html
    assert 'name="submit" value="1"' in html
    plain = FormActions("Save changes").render(None, {})
    assert "name=" not in plain
