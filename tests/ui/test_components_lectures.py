from types import SimpleNamespace

from apps.ui.components.lectures import CountdownCard, LectureRow, ScheduleList
from tests.ui.fixtures.sample_ui import fake_lectures


def test_countdown_card_renders() -> None:
    viewer = SimpleNamespace(timezone_label="PKT")
    html = str(CountdownCard(fake_lectures()[0], viewer))
    assert "countdown-card" in html
    assert "Sample lecture" in html


def test_lecture_row_renders() -> None:
    viewer = SimpleNamespace(timezone_label="PKT")
    html = str(LectureRow(fake_lectures()[0], viewer))
    assert "lecture-row" in html


def test_schedule_list_renders() -> None:
    viewer = SimpleNamespace(timezone_label="PKT")
    html = str(ScheduleList(fake_lectures(), viewer))
    assert "schedule-list" in html
