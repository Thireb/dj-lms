"""R4c: dashboard components (Lexicon redesign)."""

from __future__ import annotations

from apps.ui.components.data import (
    Badge,
    EmptyState,
    KpiSummary,
    PersonCell,
    PersonList,
    ProgressRing,
)
from apps.ui.components.layout import HeroBanner, SectionCard


def test_progress_ring_draws_the_percent_and_names_it() -> None:
    html = str(ProgressRing(58, label="Active students"))
    assert 'role="img" aria-label="Active students: 58%"' in html
    assert ">58%</text>" in html
    assert 'stroke-dasharray="123.9 213.6"' in html  # 58% of 2 * pi * 34


def test_progress_ring_clamps_out_of_range_values() -> None:
    assert ">100%</text>" in str(ProgressRing(140))
    assert ">0%</text>" in str(ProgressRing(-5))


def test_progress_ring_tone() -> None:
    assert "stroke-indigo" in str(ProgressRing(10, tone="indigo"))
    assert "stroke-primary" in str(ProgressRing(10))


def test_kpi_summary_shows_value_label_chips_and_ring() -> None:
    html = str(
        KpiSummary(
            52, "Total students", chips=[Badge("30 active")], ring=ProgressRing(58)
        )
    )
    assert ">52</p>" in html and ">Total students</p>" in html
    assert ">30 active</span>" in html
    assert "progress-ring" in html


def test_person_list_rows_and_empty_text() -> None:
    html = str(
        PersonList([(PersonCell("Zoya Demo", "STU-1"), Badge("Active"))], title="New")
    )
    assert ">New</p>" in html and ">Zoya Demo<" in html and ">Active</span>" in html
    assert ">No one here.</p>" in str(PersonList([], empty_text="No one here."))


def test_person_list_escapes_names() -> None:
    assert "<script>" not in str(PersonList([(PersonCell("<script>"), "")]))


def test_hero_banner_stats_initials_and_actions() -> None:
    html = str(
        HeroBanner(
            "Good morning, Zoya",
            initials="ZD",
            chips=["Morning: Math"],
            stats=[(52, "Students", "30 active"), (5, "Teachers", "")],
            actions=[Badge("action")],
        )
    )
    assert ">ZD</span>" in html
    assert ">Morning: Math</li>" in html
    assert "hero-stats grid gap-2.5 sm:gap-3 grid-cols-2" in html
    assert ">Students</dt>" in html and ">30 active</dd>" in html
    assert html.count("<dd") == 3  # no empty note for Teachers
    assert ">action</span>" in html


def test_hero_banner_without_stats_has_one_column() -> None:
    html = str(HeroBanner("Institute"))
    assert "hero-stats" not in html
    assert "lg:grid-cols-[" not in html


def test_section_card_icon_is_optional() -> None:
    assert "bg-primary-50 text-primary" in str(SectionCard("A", "b", icon="users"))
    assert "<svg" not in str(SectionCard("A", "b"))


def test_empty_state_can_drop_its_frame() -> None:
    assert "border-dashed" in str(EmptyState("Nothing"))
    assert "border-dashed" not in str(EmptyState("Nothing", framed=False))
