from datetime import datetime
from zoneinfo import ZoneInfo

from apps.ui.components.actions import PostButton
from apps.ui.components.lectures import (
    CountdownCard,
    LectureRow,
    scheduled_at_to_iso,
)

ISO = "2026-08-16T15:00:00+00:00"


def test_countdown_card_renders() -> None:
    html = str(
        CountdownCard(
            "Sample lecture",
            ISO,
            when="Sun 16 Aug 2026, 8:00 PM to 9:00 PM PKT",
            detail="Morning · Math",
            action=PostButton("Join", "/student/lectures/1/join/", new_tab=True),
            refresh_url="/student/up-next/",
        )
    )
    assert "countdown-card" in html
    assert "Sample lecture" in html
    assert "8:00 PM to 9:00 PM PKT" in html
    assert 'action="/student/lectures/1/join/"' in html
    assert 'target="_blank" rel="noopener noreferrer"' in html
    assert 'hx-get="/student/up-next/" hx-trigger="every 30s"' in html


def test_countdown_card_without_refresh_does_not_poll() -> None:
    html = str(CountdownCard("Sample", ISO))
    assert "hx-get" not in html


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


def test_scheduled_at_to_iso_year_one_positive_offset_returns_empty() -> None:
    assert scheduled_at_to_iso("0001-01-01T00:00:00+01:00") == ""
    aware = datetime(1, 1, 1, tzinfo=ZoneInfo("Europe/Paris"))
    assert scheduled_at_to_iso(aware) == ""


def test_scheduled_at_to_iso_converts_offset_to_utc() -> None:
    local = datetime(2026, 8, 16, 20, 0, 0, tzinfo=ZoneInfo("Asia/Karachi"))
    assert scheduled_at_to_iso(local) == "2026-08-16T15:00:00+00:00"
    assert (
        scheduled_at_to_iso("2026-08-16T20:00:00+05:00") == "2026-08-16T15:00:00+00:00"
    )


def test_countdown_card_malicious_scheduled_at_not_in_alpine_expression() -> None:
    html = str(CountdownCard("Safe title", "');alert(document.domain);//"))
    assert "countdownCard('" not in html
    assert 'x-data="countdownCard"' in html
    assert "alert(document.domain)" not in html
    assert 'data-scheduled-at=""' in html


def test_countdown_card_valid_iso_in_data_attribute() -> None:
    html = str(CountdownCard("Sample", ISO))
    assert f'data-scheduled-at="{ISO}"' in html


def test_countdown_card_escapes_title() -> None:
    xss = "<script>alert('x')</script>"
    html = str(CountdownCard(xss, ISO, when=xss, detail=xss))
    assert xss not in html
    assert "&lt;script&gt;" in html


def test_countdown_card_refuses_unsafe_refresh_url() -> None:
    html = str(CountdownCard("Sample", ISO, refresh_url="javascript:alert(1)"))
    assert "javascript:" not in html
    assert "hx-get" not in html


def test_lecture_row_renders() -> None:
    html = str(LectureRow("Algebra", "Mon 17 Aug 2026", detail="Morning · Math"))
    assert "lecture-row" in html
    assert "Morning · Math" in html


def _day(day, *items, **flags):
    from apps.ui.components.lectures import CalendarDay

    return CalendarDay(day=day, items=list(items), **flags)


def _week(start=None, **items_by_offset):
    from datetime import date, timedelta

    start = start or date(2026, 10, 12)
    return [
        _day(start + timedelta(days=n), *items_by_offset.get(f"d{n}", []))
        for n in range(7)
    ]


def test_calendar_week_shows_days_items_and_links() -> None:
    from apps.ui.components.lectures import Calendar, CalendarItem

    item = CalendarItem("10:00 AM to 11:00 AM PKT", "Algebra", url="/teacher/x/")
    html = str(
        Calendar(
            _week(d2=[item]),
            label="12 to 18 Oct 2026",
            previous_url="?date=2026-10-05",
            next_url="?date=2026-10-19",
            today_url="?date=2026-10-13",
        )
    )

    assert html.count('class="calendar-day ') == 7
    assert "Wed 14 Oct" in html
    assert '<a href="/teacher/x/"' in html
    assert html.count(">No lectures<") == 6
    assert 'aria-label="Previous week"' in html
    assert 'href="?date=2026-10-19"' in html


def test_calendar_item_with_unsafe_link_is_plain_text() -> None:
    from apps.ui.components.lectures import Calendar, CalendarItem

    item = CalendarItem("10:00 AM", "Algebra", url="javascript:alert(1)")
    html = str(Calendar(_week(d0=[item])))

    assert "javascript:" not in html
    assert '<div class="calendar-item' in html


def test_calendar_month_has_week_rows_and_a_phone_list() -> None:
    from datetime import date, timedelta

    from apps.ui.components.lectures import Calendar, CalendarItem

    first = date(2026, 9, 28)
    days = [
        _day(
            first + timedelta(days=n),
            *(
                [CalendarItem("9:00 AM", "Busy day")]
                if n in (3, 35)  # 1 Oct and 2 Nov
                else []
            ),
            in_month=(first + timedelta(days=n)).month == 10,
            is_today=n == 15,
        )
        for n in range(42)
    ]
    html = str(Calendar(days, view="month", label="October 2026"))
    phone = html.split("calendar-agenda", 1)[1]

    assert html.count('last:border-b-0">') == 6
    assert html.count('aria-current="date"') == 1
    assert "Thu 1 Oct" in phone
    assert "Mon 2 Nov" not in phone  # outside the month


def test_calendar_month_with_nothing_says_so() -> None:
    from apps.ui.components.lectures import Calendar

    html = str(Calendar(_week(), view="month", empty_text="No lectures this month."))

    assert "No lectures this month." in html
