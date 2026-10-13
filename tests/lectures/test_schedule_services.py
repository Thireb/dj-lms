"""Recurring schedules: checks, generation, edit, extend, stop (roadmap 3.2)."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from apps.core.tenancy import tenant_context
from apps.institutes.models import Institute, InstituteSettings
from apps.lectures.models import (
    Lecture,
    LectureStatus,
    RecurringSchedule,
    ScheduleStatus,
)
from apps.lectures.services import (
    create_schedule,
    extend_schedule,
    generate_lectures,
    occurrences,
    preview_schedule,
    stop_schedule,
    update_lecture,
    update_schedule,
)
from apps.lectures.tasks import extend_all_schedules, generate_schedule_lectures
from apps.people.models import ProfileStatus, TeacherProfile
from django.core.exceptions import ValidationError
from django.utils import timezone

from tests.lectures.conftest import (
    KARACHI,
    add_lecture,
    add_schedule,
    details,
    karachi_today,
    put_at,
    schedule_details,
    schedule_lectures,
)

PKT = ZoneInfo(KARACHI)


def _errors(call, *args, **kwargs) -> dict[str, list[str]]:
    with pytest.raises(ValidationError) as error:
        call(*args, **kwargs)
    return error.value.message_dict


def _create(school, **fields):
    institute = school.morning.institute
    with tenant_context(institute):
        return create_schedule(institute, schedule_details(school, **fields))


def _in_context(school, call, *args, **kwargs):
    with tenant_context(school.morning.institute):
        return call(*args, **kwargs)


def _set_horizon(institute: Institute, weeks: int) -> None:
    # unscoped: test set-up outside a tenant context.
    InstituteSettings.unscoped.update_or_create(
        institute=institute,
        defaults={"recurring_lecture_horizon_weeks": weeks},
    )


# Dates


def test_occurrences_keep_the_wall_clock_time_across_a_clock_change() -> None:
    class Source:
        time_zone = "Europe/London"
        weekdays = [6]  # Sundays
        start_time = time(10, 0)

    # The UK moves its clocks forward on 29 March 2026.
    starts = occurrences(Source, date(2026, 3, 22), date(2026, 3, 29))

    utc = [start.astimezone(ZoneInfo("UTC")).hour for start in starts]
    assert [start.hour for start in starts] == [10, 10]
    assert utc == [10, 9]


# Create and generate


@pytest.mark.django_db
def test_saving_makes_one_lecture_per_chosen_day(
    school, django_capture_on_commit_callbacks
) -> None:
    with django_capture_on_commit_callbacks(execute=True):
        schedule = _create(school, weekdays=[0, 2, 4])
    schedule.refresh_from_db()
    lectures = schedule_lectures(schedule)

    days = {timezone.localtime(lec.starts_at, PKT).weekday() for lec in lectures}
    assert days <= {0, 2, 4}
    assert 2 <= len(lectures) <= 4  # 7 days hold 3 of these weekdays, 2 to 4
    assert all(
        timezone.localtime(lec.starts_at, PKT).time() == time(10) for lec in lectures
    )
    assert all(lec.title == "Daily algebra" for lec in lectures)
    with tenant_context(school.morning.institute):
        assert list(lectures[0].subjects.all()) == [school.math]
    assert schedule.generated_until == schedule.end_date


@pytest.mark.django_db
def test_lectures_are_made_up_to_the_horizon_only(school) -> None:
    _set_horizon(school.morning.institute, 1)
    start = karachi_today() + timedelta(days=1)

    schedule = add_schedule(school, end_date=start + timedelta(days=60))

    last = schedule_lectures(schedule)[-1].starts_at
    assert timezone.localtime(last, PKT).date() <= karachi_today() + timedelta(weeks=1)
    assert schedule.generated_until == karachi_today() + timedelta(weeks=1)


@pytest.mark.django_db
def test_generating_twice_makes_no_duplicates(school) -> None:
    schedule = add_schedule(school)
    _in_context(school, generate_lectures, schedule)
    schedule.generated_until = None
    _in_context(school, generate_lectures, schedule)

    assert len(schedule_lectures(schedule)) == 7


@pytest.mark.django_db
def test_the_nightly_run_adds_the_next_days(school) -> None:
    _set_horizon(school.morning.institute, 1)
    start = karachi_today() + timedelta(days=1)
    schedule = add_schedule(school, end_date=start + timedelta(days=20))
    before = len(schedule_lectures(schedule))

    a_week_later = timezone.now() + timedelta(days=7)
    result = _in_context(school, generate_lectures, schedule, now=a_week_later)

    assert result.created == 7
    assert len(schedule_lectures(schedule)) == before + 7


@pytest.mark.django_db
def test_a_busy_teacher_date_is_skipped(school) -> None:
    tomorrow_ten = datetime.combine(
        karachi_today() + timedelta(days=1), time(10, 30), tzinfo=PKT
    )
    add_lecture(school, title="Exam", starts_at=tomorrow_ten)

    schedule = _create(school)
    result = _in_context(school, generate_lectures, schedule)

    assert result.created == 6
    assert result.skipped == 1


@pytest.mark.django_db
def test_preview_lists_the_lectures_and_marks_clashes(school) -> None:
    tomorrow_ten = datetime.combine(
        karachi_today() + timedelta(days=1), time(10, 0), tzinfo=PKT
    )
    exam = add_lecture(school, title="Exam", starts_at=tomorrow_ten)
    _set_horizon(school.morning.institute, 1)
    start = karachi_today() + timedelta(days=1)
    institute = school.morning.institute

    preview = _in_context(
        school,
        preview_schedule,
        institute,
        schedule_details(school, end_date=start + timedelta(days=20)),
    )

    assert preview.planned[0].clash == exam
    assert preview.created_count == len(preview.planned) - 1
    assert preview.later_count > 0
    assert preview.horizon_weeks == 1
    assert not RecurringSchedule.unscoped.exists()  # a preview saves nothing


@pytest.mark.django_db
def test_today_start_time_that_has_passed_is_skipped(school) -> None:
    now = timezone.now()
    earlier = timezone.localtime(now, PKT) - timedelta(hours=1)
    if earlier.date() != karachi_today():
        pytest.skip("just after midnight in Karachi")

    schedule = add_schedule(
        school,
        start_date=karachi_today(),
        end_date=karachi_today(),
        start_time=earlier.time().replace(second=0, microsecond=0),
    )

    assert schedule_lectures(schedule) == []


# Checks


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("fields", "field", "message"),
    [
        ({"weekdays": []}, "weekdays", "Choose at least one day."),
        ({"weekdays": [7]}, "weekdays", "Choose at least one day."),
        ({"title": " "}, "title", "Enter a title."),
        ({"duration_minutes": 5}, "duration_minutes", "Enter a duration from 10"),
        ({"meeting_url": ""}, "meeting_url", "Paste the meeting link"),
    ],
)
def test_bad_values_are_refused(school, fields, field, message) -> None:
    errors = _errors(_create, school, **fields)

    assert errors[field][0].startswith(message)


@pytest.mark.django_db
def test_date_rules(school) -> None:
    today = karachi_today()

    past = _errors(_create, school, start_date=today - timedelta(days=1))
    backwards = _errors(
        _create, school, start_date=today + timedelta(days=5), end_date=today
    )
    too_long = _errors(_create, school, end_date=today + timedelta(days=400))
    no_day = _errors(
        _create,
        school,
        weekdays=[(today + timedelta(days=3)).weekday()],
        start_date=today + timedelta(days=1),
        end_date=today + timedelta(days=2),
    )

    assert past["start_date"] == ["Choose a start date from today on."]
    assert backwards["end_date"] == ["The end date is before the start date."]
    assert too_long["end_date"] == ["A schedule can run for one year at most."]
    assert no_day["weekdays"] == ["None of these days falls between the dates."]


@pytest.mark.django_db
def test_teacher_must_teach_the_subjects(school) -> None:
    errors = _errors(_create, school, subjects=[school.physics])

    assert errors["subjects"] == [
        f"{school.teacher_1} does not teach Physics in Morning."
    ]


@pytest.mark.django_db
def test_unknown_time_zone_is_refused(school) -> None:
    assert _errors(_create, school, time_zone="Mars/Base")["__all__"] == [
        "Unknown time zone."
    ]


@pytest.mark.django_db
def test_no_lectures_once_the_teacher_no_longer_fits(school) -> None:
    schedule = _create(school)
    # unscoped: test set-up outside a tenant context.
    TeacherProfile.unscoped.filter(pk=school.teacher_1.pk).update(
        status=ProfileStatus.INACTIVE
    )
    schedule.teacher.refresh_from_db()

    result = _in_context(school, generate_lectures, schedule)

    assert result.created == 0
    assert result.skipped == 7
    assert schedule.generated_until is None


# Edit, extend, stop


@pytest.mark.django_db
def test_edit_remakes_future_lectures_and_keeps_ones_edited_alone(school) -> None:
    schedule = add_schedule(school)
    lectures = schedule_lectures(schedule)
    alone = lectures[2]
    _in_context(
        school,
        update_lecture,
        alone,
        details(school, title="Moved one", starts_at=alone.starts_at),
    )
    started = put_at(lectures[0], timezone.now() - timedelta(minutes=10))

    removed = _in_context(
        school,
        update_schedule,
        schedule,
        schedule_details(school, start_time=time(15, 0)),
    )
    _in_context(school, generate_lectures, schedule)

    after = schedule_lectures(schedule)
    alone.refresh_from_db()
    assert removed == 5  # 7 less the started one and the one edited alone
    assert alone.follows_schedule is False and alone.title == "Moved one"
    assert started in after
    remade = [lec for lec in after if lec.follows_schedule and lec != started]
    # The started lecture was moved to today, so its old day is free again:
    # 7 days less the day edited alone.
    assert len(remade) == 6
    assert {timezone.localtime(lec.starts_at, PKT).hour for lec in remade} == {15}


@pytest.mark.django_db
def test_extend_adds_dates(school) -> None:
    schedule = add_schedule(school)

    _in_context(
        school, extend_schedule, schedule, schedule.end_date + timedelta(days=3)
    )
    _in_context(school, generate_lectures, schedule)

    assert len(schedule_lectures(schedule)) == 10


@pytest.mark.django_db
def test_extend_rules(school) -> None:
    schedule = add_schedule(school)

    same = _errors(_in_context, school, extend_schedule, schedule, schedule.end_date)
    far = _errors(
        _in_context,
        school,
        extend_schedule,
        schedule,
        schedule.start_date + timedelta(days=400),
    )

    assert same["end_date"] == ["Choose a date after the current end date."]
    assert far["end_date"] == ["A schedule can run for one year at most."]


@pytest.mark.django_db
def test_stop_cancels_lectures_not_started_and_blocks_changes(school) -> None:
    schedule = add_schedule(school)
    started = put_at(
        schedule_lectures(schedule)[0], timezone.now() - timedelta(minutes=5)
    )

    cancelled = _in_context(school, stop_schedule, schedule)

    statuses = [lec.status for lec in schedule_lectures(schedule)]
    assert cancelled == 6
    assert statuses.count(LectureStatus.CANCELLED) == 6
    started.refresh_from_db()
    assert started.status == LectureStatus.SCHEDULED
    assert schedule.status == ScheduleStatus.STOPPED
    assert _in_context(school, generate_lectures, schedule).created == 0
    assert "__all__" in _errors(
        _in_context, school, update_schedule, schedule, schedule_details(school)
    )
    assert "__all__" in _errors(
        _in_context,
        school,
        extend_schedule,
        schedule,
        schedule.end_date + timedelta(days=7),
    )


@pytest.mark.django_db
def test_editing_a_schedule_lecture_marks_it_as_edited_alone(school) -> None:
    lecture = schedule_lectures(add_schedule(school))[0]

    _in_context(
        school,
        update_lecture,
        lecture,
        details(school, title="Special", starts_at=lecture.starts_at),
    )

    lecture.refresh_from_db()
    assert lecture.follows_schedule is False
    assert lecture.schedule is not None


# Scopes


@pytest.mark.django_db
def test_schedule_scopes(school, admin_a, admin_b) -> None:
    add_schedule(school)

    def titles(user):
        return list(
            RecurringSchedule.objects.for_user(user).values_list("title", flat=True)
        )

    assert titles(admin_a) == ["Daily algebra"]
    assert titles(admin_b) == []
    assert titles(school.teacher_1.user) == ["Daily algebra"]
    assert titles(school.teacher_2.user) == []
    assert titles(school.student_1.user) == []
    assert titles(school.guardian_1.user) == []


@pytest.mark.django_db
def test_no_tenant_context_sees_no_schedules(school) -> None:
    add_schedule(school)

    assert RecurringSchedule.objects.count() == 0


# Tasks


@pytest.mark.django_db
def test_generate_task_skips_inactive_institutes_and_missing_rows(school) -> None:
    schedule = _create(school)
    institute = school.morning.institute

    assert generate_schedule_lectures(institute.pk, 999999) == 0
    Institute.objects.filter(pk=institute.pk).update(is_active=False)
    assert generate_schedule_lectures(institute.pk, schedule.pk) == 0
    Institute.objects.filter(pk=institute.pk).update(is_active=True)
    assert generate_schedule_lectures(institute.pk, schedule.pk) == 7


@pytest.mark.django_db
def test_nightly_task_extends_active_schedules_only(school) -> None:
    _set_horizon(school.morning.institute, 1)
    start = karachi_today() + timedelta(days=1)
    active = add_schedule(school, end_date=start + timedelta(days=20))
    stopped = add_schedule(
        school,
        title="Stopped",
        start_time=time(18, 0),
        end_date=start + timedelta(days=20),
    )
    _in_context(school, stop_schedule, stopped)
    before = len(schedule_lectures(active))
    _set_horizon(school.morning.institute, 3)

    created = extend_all_schedules()

    assert created == len(schedule_lectures(active)) - before > 0
    assert (
        Lecture.unscoped.filter(schedule=stopped)
        .exclude(status=LectureStatus.CANCELLED)
        .count()
        == 0
    )
