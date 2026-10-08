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
    assert "AL" in html


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
