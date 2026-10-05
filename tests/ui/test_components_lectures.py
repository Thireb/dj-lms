from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from apps.ui.components.lectures import (
    CountdownCard,
    LectureRow,
    ScheduleList,
    scheduled_at_to_iso,
)
from tests.ui.fixtures.sample_ui import fake_lectures


def test_countdown_card_renders() -> None:
    viewer = SimpleNamespace(timezone_label="PKT")
    html = str(CountdownCard(fake_lectures()[0], viewer))
    assert "countdown-card" in html
    assert "Sample lecture" in html


def test_scheduled_at_to_iso_rejects_non_datetime_strings() -> None:
    assert (
        scheduled_at_to_iso("2026-08-16T15:00:00+00:00") == "2026-08-16T15:00:00+00:00"
    )
    assert scheduled_at_to_iso("');alert(document.domain);//") == ""


def test_scheduled_at_to_iso_naive_datetime_and_string_use_utc() -> None:
    naive_dt = datetime(2026, 8, 16, 15, 0, 0)
    assert scheduled_at_to_iso(naive_dt) == "2026-08-16T15:00:00+00:00"
    assert scheduled_at_to_iso("2026-08-16 15:00") == "2026-08-16T15:00:00+00:00"


def test_scheduled_at_to_iso_impossible_dates_return_empty() -> None:
    assert scheduled_at_to_iso("2026-02-30T10:00:00") == ""
    assert scheduled_at_to_iso("2026-13-01T10:00:00") == ""


def test_scheduled_at_to_iso_converts_offset_to_utc() -> None:
    local = datetime(2026, 8, 16, 20, 0, 0, tzinfo=ZoneInfo("Asia/Karachi"))
    assert scheduled_at_to_iso(local) == "2026-08-16T15:00:00+00:00"
    assert (
        scheduled_at_to_iso("2026-08-16T20:00:00+05:00") == "2026-08-16T15:00:00+00:00"
    )


def test_countdown_card_malicious_scheduled_at_not_in_alpine_expression() -> None:
    payload = "');alert(document.domain);//"
    lecture = SimpleNamespace(
        title="Safe title",
        scheduled_at=payload,
        meeting_link="https://meet.example.invalid/x",
    )
    viewer = SimpleNamespace(timezone_label="PKT")
    html = str(CountdownCard(lecture, viewer))
    assert "countdownCard('" not in html
    assert 'x-data="countdownCard"' in html
    assert "alert(document.domain)" not in html
    assert 'data-scheduled-at=""' in html


def test_countdown_card_valid_iso_in_data_attribute() -> None:
    iso = "2026-08-16T15:00:00+00:00"
    lecture = SimpleNamespace(
        title="Sample",
        scheduled_at=iso,
        meeting_link="https://meet.example.invalid/x",
    )
    html = str(CountdownCard(lecture, SimpleNamespace(timezone_label="PKT")))
    assert f'data-scheduled-at="{iso}"' in html


def test_countdown_card_escapes_title() -> None:
    xss = "<script>alert('x')</script>"
    lecture = SimpleNamespace(
        title=xss,
        scheduled_at="2026-08-16T15:00:00+00:00",
        meeting_link="https://meet.example.invalid/x",
    )
    viewer = SimpleNamespace(timezone_label="PKT")
    html = str(CountdownCard(lecture, viewer))
    assert xss not in html
    assert "&lt;script&gt;" in html


def test_lecture_row_renders() -> None:
    viewer = SimpleNamespace(timezone_label="PKT")
    html = str(LectureRow(fake_lectures()[0], viewer))
    assert "lecture-row" in html


def test_schedule_list_renders() -> None:
    viewer = SimpleNamespace(timezone_label="PKT")
    html = str(ScheduleList(fake_lectures(), viewer))
    assert "schedule-list" in html
