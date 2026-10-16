from apps.ui.components.actions import Button
from apps.ui.components.data import (
    Avatar,
    Badge,
    ChartCard,
    Column,
    DataTable,
    EmptyState,
    ProgressBar,
    StatCard,
)


def test_stat_card_renders() -> None:
    html = str(StatCard("12", "Students", note="Today"))
    assert "12" in html
    assert "stat-card" in html


def test_data_table_renders_rows() -> None:
    table = DataTable(
        rows=[{"name": "Alex"}],
        columns=[Column("name", "Name")],
    )
    html = str(table)
    assert "Alex" in html
    assert "data-table" in html


def test_badge_renders() -> None:
    html = str(Badge("Active", tone="success"))
    assert "Active" in html
    assert "badge" in html


def test_avatar_renders_initials() -> None:
    html = str(Avatar("Alex Sample"))
    assert "avatar" in html
    assert ">AS<" in html  # first letters of the first two words
    assert str(Avatar("Hiba Rauf")).count('title="Hiba Rauf"') == 1


def test_progress_bar_renders() -> None:
    html = str(ProgressBar(50, label="Done"))
    assert "progress-bar" in html
    assert "Done" in html


def test_chart_card_renders_canvas_without_global_script() -> None:
    html = str(ChartCard("Trend", "chart-1", "/data/"))
    assert "chart-card" in html
    assert "chart-1" in html
    assert "chart.umd.min.js" not in html


def test_empty_state_renders() -> None:
    html = str(EmptyState("Nothing here", action=Button("Add item", url="#")))
    assert "Nothing here" in html
    assert "empty-state" in html


def test_badge_tones_use_theme_colors() -> None:
    assert "text-success" in str(Badge("Active", tone="success"))
    assert "text-danger" in str(Badge("Inactive", tone="danger"))
    assert "text-warning" in str(Badge("Pending", tone="warning"))
    assert "text-info" in str(Badge("Live", tone="info"))
    assert "text-muted" in str(Badge("Draft", tone="neutral"))


def test_detail_list_renders_pairs_components_and_a_dash() -> None:
    from apps.ui.components.data import Badge, DetailList

    html = str(
        DetailList(
            [
                ("Status", Badge("Live", tone="success")),
                ("Batch", "Morning"),
                ("Notes", ""),
                ("Unsafe", "<script>x</script>"),
            ]
        )
    )

    assert "<dt" in html and ">Batch</dt>" in html
    assert "badge" in html and ">Live<" in html
    assert '<span class="text-muted">-</span>' in html
    assert "<script>x" not in html


def test_text_block_keeps_lines_and_escapes() -> None:
    from apps.ui.components.data import TextBlock

    html = str(TextBlock("Line one.\n<b>Line two</b>"))
    assert "Line one.\n&lt;b&gt;Line two&lt;/b&gt;" in html
    assert "whitespace-pre-line" in html
    assert "break-words" in html
    assert str(TextBlock("", empty_text="No feedback.")).count("No feedback.") == 1
    assert str(TextBlock("")).strip() == ""


def test_message_list_escapes_and_marks_my_messages() -> None:
    from types import SimpleNamespace

    from apps.ui.components import MessageList

    rows = [
        SimpleNamespace(author="Sam", when="Fri", body="<b>Hi</b>\nthere", mine=False),
        SimpleNamespace(author="You", when="Fri", body="Hello", mine=True),
    ]
    html = str(MessageList(rows))
    assert "&lt;b&gt;Hi&lt;/b&gt;" in html and "whitespace-pre-line" in html
    assert html.count("justify-end") == 1
