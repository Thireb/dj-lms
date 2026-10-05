from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

import pytest
from apps.ui.components.actions import Button, ConfirmDialog, QuickAction, Toast
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
from apps.ui.components.layout import HeroBanner, Modal, PageHeader, SectionCard
from apps.ui.components.lectures import CountdownCard, LectureRow, ScheduleList
from apps.ui.components.nav import FilterBar
from apps.ui.components.pdf import PdfHeader

XSS = "<script>alert('x')</script>"
ESCAPED_FRAGMENT = "&lt;script&gt;"


def _lecture(**overrides):
    base = SimpleNamespace(
        title="Lecture",
        scheduled_at="2026-08-16T15:00:00+00:00",
        meeting_link="https://meet.example.invalid/x",
        status="scheduled",
        day="Mon 16 Aug 2026",
    )
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


@pytest.mark.parametrize(
    ("component_factory",),
    [
        (lambda: Badge(XSS),),
        (lambda: StatCard(XSS, XSS, note=XSS),),
        (lambda: Avatar(XSS),),
        (lambda: ProgressBar(50, label=XSS),),
        (lambda: ChartCard(XSS, "chart-xss", "/data/"),),
        (lambda: EmptyState(XSS, text=XSS),),
        (lambda: Button(XSS),),
        (lambda: QuickAction(XSS, "plus", "#"),),
        (lambda: ConfirmDialog(XSS, XSS, url="#"),),
        (lambda: Toast(XSS),),
        (lambda: HeroBanner(XSS, subtitle=XSS, chips=[XSS]),),
        (lambda: PageHeader(XSS, breadcrumb=[XSS]),),
        (lambda: SectionCard(XSS, body=XSS, link_label=XSS),),
        (lambda: Modal("demo", XSS, body=XSS),),
        (
            lambda: DataTable(
                rows=[{"name": XSS}],
                columns=[Column("name", XSS)],
                empty_title=XSS,
            ),
        ),
        (
            lambda: PdfHeader(
                SimpleNamespace(name=XSS, timezone=XSS),
            ),
        ),
        (
            lambda: CountdownCard(
                _lecture(title=XSS), SimpleNamespace(timezone_label="PKT")
            ),
        ),
        (lambda: LectureRow(_lecture(title=XSS, status=XSS), SimpleNamespace()),),
        (
            lambda: ScheduleList(
                [_lecture(title=XSS, day=XSS)],
                SimpleNamespace(),
            ),
        ),
        (
            lambda: FilterBar(
                filters=[
                    SimpleNamespace(name="q", label=XSS, placeholder=XSS),
                ],
            ),
        ),
    ],
    ids=[
        "badge",
        "stat_card",
        "avatar",
        "progress_bar",
        "chart_card",
        "empty_state",
        "button",
        "quick_action",
        "confirm_dialog",
        "toast",
        "hero_banner",
        "page_header",
        "section_card",
        "modal",
        "data_table",
        "pdf_header",
        "countdown_card",
        "lecture_row",
        "schedule_list",
        "filter_bar",
    ],
)
def test_component_text_props_are_escaped(component_factory) -> None:
    html = str(component_factory())
    assert XSS not in html
    assert ESCAPED_FRAGMENT in html


def test_mark_safe_and_safe_filter_only_in_allowed_locations() -> None:
    root = Path(__file__).resolve().parents[2]
    allowed_mark_safe = {root / "apps/ui/components/base.py"}
    allowed_safe_filter = {root / "apps/ui/templates/ui/forms/whole_uni_form.html"}
    scan_roots = [root / "apps", root / "templates"]
    mark_safe_needle = "mark_" + "safe"

    mark_safe_hits: list[Path] = []
    safe_filter_hits: list[Path] = []

    for scan_root in scan_roots:
        for path in scan_root.rglob("*"):
            if path.suffix not in {".py", ".html"}:
                continue
            text = path.read_text(encoding="utf-8")
            if mark_safe_needle in text and path not in allowed_mark_safe:
                mark_safe_hits.append(path)
            if re.search(r"\|safe\b", text) and path not in allowed_safe_filter:
                safe_filter_hits.append(path)

    assert not mark_safe_hits, f"mark_safe outside Component.render: {mark_safe_hits}"
    assert not safe_filter_hits, f"|safe outside whole_uni_form: {safe_filter_hits}"
