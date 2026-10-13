"""Lecture services: checks, overlaps and lists (SPEC 4.5 and 6.4)."""

from __future__ import annotations

from datetime import timedelta
from zoneinfo import ZoneInfo

import pytest
from apps.academics.models import Batch, Subject, TeacherBatchSubject
from apps.core.tenancy import TenantContextError, tenant_context
from apps.lectures.models import DeliveryMode, Lecture, LectureStatus
from apps.lectures.providers import provider_for
from apps.lectures.services import create_lecture, list_lectures, update_lecture
from apps.people.models import ProfileStatus, TeacherProfile
from django.core.exceptions import ValidationError
from django.utils import timezone

from tests.lectures.conftest import MEET_URL, add_lecture, details, put_at, soon
from tests.people.conftest import student
from tests.school import link_guardian, link_student


def _create(school, **fields):
    institute = school.morning.institute
    with tenant_context(institute):
        return create_lecture(institute, details(school, **fields))


def _update(lecture, school, **fields):
    with tenant_context(lecture.institute):
        return update_lecture(lecture, details(school, **fields))


def _errors(call, *args, **kwargs) -> dict[str, list[str]]:
    with pytest.raises(ValidationError) as error:
        call(*args, **kwargs)
    return error.value.message_dict


# Create


@pytest.mark.django_db
def test_create_saves_every_field(school) -> None:
    starts_at = soon(days=2)
    saved = _create(
        school,
        starts_at=starts_at,
        title="  Fractions  ",
        description=" Bring a ruler ",
    )

    lecture = saved.lecture
    assert lecture.title == "Fractions"
    assert lecture.description == "Bring a ruler"
    assert lecture.starts_at == starts_at
    assert lecture.meeting_url == MEET_URL
    assert lecture.institute == school.morning.institute
    with tenant_context(lecture.institute):
        assert list(lecture.subjects.all()) == [school.math]
    assert saved.batch_clashes == []


@pytest.mark.django_db
def test_create_needs_the_tenant_context(school) -> None:
    with pytest.raises(TenantContextError):
        create_lecture(school.morning.institute, details(school))


@pytest.mark.django_db
def test_in_person_lecture_drops_the_link(school) -> None:
    lecture = _create(school, delivery_mode=DeliveryMode.IN_PERSON).lecture

    assert lecture.meeting_url == ""


@pytest.mark.django_db
def test_teacher_must_teach_the_subject_in_that_batch(school) -> None:
    errors = _errors(_create, school, subjects=[school.math, school.physics])

    assert errors["subjects"] == [
        f"{school.teacher_1} does not teach Physics in Morning."
    ]


@pytest.mark.django_db
def test_teacher_must_teach_in_that_batch(school) -> None:
    errors = _errors(_create, school, batch=school.evening)

    assert errors["subjects"] == [f"{school.teacher_1} does not teach Math in Evening."]


@pytest.mark.django_db
def test_rows_from_another_institute_are_refused(school) -> None:
    other_teacher = school.teacher_b
    # unscoped: test set-up reads institute B's rows.
    other_batch = Batch.unscoped.get(pk=school.batch_b.pk)
    other_subject = Subject.unscoped.get(institute=school.batch_b.institute)

    assert "teacher" in _errors(_create, school, teacher=other_teacher)
    assert "batch" in _errors(_create, school, batch=other_batch)
    assert "subjects" in _errors(_create, school, subjects=[other_subject])


@pytest.mark.django_db
def test_no_subjects_is_refused(school) -> None:
    assert _errors(_create, school, subjects=[])["subjects"] == [
        "Choose at least one subject."
    ]


@pytest.mark.django_db
def test_inactive_teacher_batch_and_subject_are_refused(school) -> None:
    # unscoped: test set-up outside a tenant context.
    TeacherProfile.unscoped.filter(pk=school.teacher_1.pk).update(
        status=ProfileStatus.INACTIVE
    )
    Batch.unscoped.filter(pk=school.morning.pk).update(is_active=False)
    Subject.unscoped.filter(pk=school.math.pk).update(is_active=False)
    school.teacher_1.refresh_from_db()
    school.morning.refresh_from_db()
    school.math.refresh_from_db()

    errors = _errors(_create, school)

    assert errors["teacher"] == ["This teacher is inactive."]
    assert errors["batch"] == ["Morning is inactive."]
    assert errors["subjects"] == ["Math is inactive."]


@pytest.mark.django_db
def test_start_must_be_in_the_future(school) -> None:
    errors = _errors(_create, school, starts_at=timezone.now() - timedelta(minutes=1))

    assert errors["starts_at"] == ["Choose a start time in the future."]


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("minutes", "ok"), [(9, False), (10, True), (480, True), (481, False)]
)
def test_duration_from_10_to_480_minutes(school, minutes, ok) -> None:
    if ok:
        assert _create(school, duration_minutes=minutes).lecture.pk
    else:
        assert _errors(_create, school, duration_minutes=minutes)[
            "duration_minutes"
        ] == ["Enter a duration from 10 to 480 minutes."]


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("link", "message"),
    [
        ("", "Paste the meeting link for an online lecture."),
        ("   ", "Paste the meeting link for an online lecture."),
        ("javascript:alert(1)", "Enter a full link that starts with https://."),
        ("ftp://files.example.com/a", "Enter a full link that starts with https://."),
        ("meet.example.com/abc", "Enter a full link that starts with https://."),
    ],
)
def test_online_lecture_needs_a_web_link(school, link, message) -> None:
    assert _errors(_create, school, meeting_url=link)["meeting_url"] == [message]


@pytest.mark.django_db
def test_unknown_delivery_mode_is_refused(school) -> None:
    assert "delivery_mode" in _errors(_create, school, delivery_mode="zoom")


@pytest.mark.django_db
def test_blank_title_is_refused(school) -> None:
    assert _errors(_create, school, title="   ")["title"] == ["Enter a title."]


# Overlaps


@pytest.mark.django_db
def test_teacher_cannot_have_two_lectures_at_once(school) -> None:
    first = add_lecture(school, title="First")

    errors = _errors(_create, school, starts_at=first.starts_at + timedelta(minutes=59))

    assert errors["starts_at"][0].startswith(
        f"{school.teacher_1} already has First on "
    )


@pytest.mark.django_db
def test_back_to_back_lectures_are_fine(school) -> None:
    first = add_lecture(school, title="First")

    later = _create(school, starts_at=first.ends_at).lecture
    earlier = _create(school, starts_at=first.starts_at - timedelta(minutes=60)).lecture

    assert later.pk and earlier.pk


@pytest.mark.django_db
def test_a_cancelled_lecture_frees_the_slot(school) -> None:
    first = add_lecture(school, title="First")
    # unscoped: cancelling comes with roadmap 3.5; set the state directly.
    Lecture.unscoped.filter(pk=first.pk).update(status=LectureStatus.CANCELLED)

    assert _create(school, starts_at=first.starts_at).lecture.pk


@pytest.mark.django_db
def test_other_teachers_do_not_clash(school) -> None:
    first = add_lecture(school)

    saved = _create(
        school,
        teacher=school.teacher_2,
        batch=school.evening,
        subjects=[school.physics],
        starts_at=first.starts_at,
    )

    assert saved.batch_clashes == []


@pytest.mark.django_db
def test_same_batch_at_the_same_time_is_a_warning(school) -> None:
    with tenant_context(school.morning.institute):
        TeacherBatchSubject.objects.create(
            institute=school.morning.institute,
            teacher=school.teacher_2,
            batch=school.morning,
            subject=school.physics,
        )
    first = add_lecture(school, title="Morning math")

    saved = _create(
        school,
        title="Morning physics",
        teacher=school.teacher_2,
        subjects=[school.physics],
        starts_at=first.starts_at + timedelta(minutes=30),
    )

    assert saved.lecture.pk
    assert saved.batch_clashes == [first]


# Update


@pytest.mark.django_db
def test_update_changes_fields_and_ignores_its_own_slot(school) -> None:
    lecture = add_lecture(school)

    saved = _update(
        lecture,
        school,
        title="Algebra, part 2",
        duration_minutes=90,
        delivery_mode=DeliveryMode.IN_PERSON,
    )

    lecture.refresh_from_db()
    assert saved.lecture.pk == lecture.pk
    assert lecture.title == "Algebra, part 2"
    assert lecture.duration_minutes == 90
    assert lecture.meeting_url == ""


@pytest.mark.django_db
def test_update_keeps_a_start_time_that_has_passed(school) -> None:
    lecture = put_at(add_lecture(school), timezone.now() - timedelta(minutes=5))

    _update(lecture, school, starts_at=lecture.starts_at, title="Renamed")

    lecture.refresh_from_db()
    assert lecture.title == "Renamed"


@pytest.mark.django_db
def test_update_cannot_move_into_the_past(school) -> None:
    lecture = add_lecture(school)

    errors = _errors(
        _update, lecture, school, starts_at=timezone.now() - timedelta(hours=1)
    )

    assert errors["starts_at"] == ["Choose a start time in the future."]


@pytest.mark.django_db
def test_update_keeps_inactive_rows_already_on_the_lecture(school) -> None:
    lecture = add_lecture(school)
    # unscoped: test set-up outside a tenant context.
    Batch.unscoped.filter(pk=school.morning.pk).update(is_active=False)
    Subject.unscoped.filter(pk=school.math.pk).update(is_active=False)
    TeacherProfile.unscoped.filter(pk=school.teacher_1.pk).update(
        status=ProfileStatus.INACTIVE
    )
    for row in (school.morning, school.math, school.teacher_1):
        row.refresh_from_db()

    _update(lecture, school, title="Still here")

    lecture.refresh_from_db()
    assert lecture.title == "Still here"


@pytest.mark.django_db
def test_update_overlap_with_another_lecture_is_refused(school) -> None:
    first = add_lecture(school, title="First")
    second = add_lecture(school, title="Second", starts_at=first.ends_at)

    errors = _errors(_update, second, school, starts_at=first.starts_at)

    assert errors["starts_at"][0].startswith(f"{school.teacher_1} already has First")


@pytest.mark.django_db
@pytest.mark.parametrize(
    "status", [LectureStatus.LIVE, LectureStatus.FINISHED, LectureStatus.CANCELLED]
)
def test_only_scheduled_lectures_can_be_edited(school, status) -> None:
    lecture = add_lecture(school)
    # unscoped: states come with roadmap 3.5; set the state directly.
    Lecture.unscoped.filter(pk=lecture.pk).update(status=status)
    lecture.refresh_from_db()

    errors = _errors(_update, lecture, school)

    assert errors["__all__"] == ["Only a scheduled lecture can be edited."]


# Lists


def _list_titles(user, **kwargs) -> list[str]:
    return [lecture.title for lecture in list_lectures(user, **kwargs)]


@pytest.mark.django_db
def test_list_views_split_upcoming_past_and_all(school) -> None:
    now = timezone.now()
    put_at(add_lecture(school, title="Running"), now - timedelta(minutes=30))
    put_at(add_lecture(school, title="Ended"), now - timedelta(days=3))
    add_lecture(school, title="Next week", starts_at=soon(days=7))
    user = school.teacher_1.user

    assert _list_titles(user, show="upcoming", now=now) == ["Running", "Next week"]
    assert _list_titles(user, show="past", now=now) == ["Ended"]
    assert _list_titles(user, show="all", now=now) == ["Ended", "Running", "Next week"]
    assert "Next week" not in _list_titles(user, show="today", now=now)


@pytest.mark.django_db
def test_today_follows_the_viewer_time_zone(school) -> None:
    lecture = add_lecture(school, title="Late", starts_at=soon(days=1, hour=21))
    # At 15:00 UTC (20:00 in Karachi, UTC+5), a 21:00 UTC lecture is today
    # in UTC but 02:00 tomorrow in Karachi.
    evening = lecture.starts_at - timedelta(hours=6)
    user = school.teacher_1.user

    with timezone.override("UTC"):
        assert _list_titles(user, show="today", now=evening) == ["Late"]
    with timezone.override("Asia/Karachi"):
        assert _list_titles(user, show="today", now=evening) == []


@pytest.mark.django_db
def test_today_uses_the_viewer_date_not_the_utc_date(school) -> None:
    lecture = add_lecture(school, title="Early", starts_at=soon(days=2, hour=3))
    # At 20:00 UTC it is already 01:00 the next day in Karachi, the day of
    # this 03:00 UTC (08:00 Karachi) lecture.
    late_evening = lecture.starts_at - timedelta(hours=7)
    user = school.teacher_1.user

    with timezone.override("Asia/Karachi"):
        assert _list_titles(user, show="today", now=late_evening) == ["Early"]
    with timezone.override("UTC"):
        assert _list_titles(user, show="today", now=late_evening) == []


@pytest.mark.django_db
def test_past_list_is_newest_first(school) -> None:
    now = timezone.now()
    put_at(add_lecture(school, title="Older"), now - timedelta(days=5))
    put_at(add_lecture(school, title="Newer"), now - timedelta(days=2))

    assert _list_titles(school.teacher_1.user, show="past") == ["Newer", "Older"]


@pytest.mark.django_db
def test_list_filters(school, admin_a) -> None:
    add_lecture(school, title="Math")
    add_lecture(
        school,
        title="Physics",
        teacher=school.teacher_2,
        batch=school.evening,
        subjects=[school.physics],
    )

    assert _list_titles(admin_a, teacher_id=school.teacher_2.pk) == ["Physics"]
    assert _list_titles(admin_a, batch_id=school.morning.pk) == ["Math"]
    assert _list_titles(admin_a, subject_id=school.physics.pk) == ["Physics"]
    assert _list_titles(admin_a, status="cancelled") == []
    assert len(_list_titles(admin_a, status="not-a-status")) == 2


@pytest.mark.django_db
def test_date_range_uses_viewer_days_and_includes_both_ends(school, admin_a) -> None:
    """Lectures at 23:00 UTC are on the next day in Karachi (UTC+5)."""
    first = add_lecture(school, title="First", starts_at=soon(days=2, hour=23))
    add_lecture(school, title="Second", starts_at=soon(days=3, hour=23))
    add_lecture(school, title="Third", starts_at=soon(days=4, hour=23))
    karachi_day = timezone.localtime(first.starts_at, ZoneInfo("Asia/Karachi")).date()
    later = karachi_day + timedelta(days=1)

    with timezone.override("Asia/Karachi"):
        assert _list_titles(admin_a, date_from=later) == ["Second", "Third"]
        assert _list_titles(admin_a, date_to=later) == ["First", "Second"]
        assert _list_titles(admin_a, date_from=later, date_to=later) == ["Second"]
    with timezone.override("UTC"):
        assert _list_titles(admin_a, date_from=later, date_to=later) == ["Third"]


@pytest.mark.django_db
def test_student_filter_keeps_one_child(school, institute_a) -> None:
    """A guardian of two children sees one child's lectures at a time."""
    link_guardian(school.student_2, "g1-a@example.com")
    add_lecture(school, title="Math")
    add_lecture(
        school,
        title="Physics",
        teacher=school.teacher_2,
        batch=school.evening,
        subjects=[school.physics],
    )
    guardian = school.guardian_1.user

    assert _list_titles(guardian) == ["Math", "Physics"]
    assert _list_titles(guardian, student_id=school.student_1.pk) == ["Math"]
    assert _list_titles(guardian, student_id=school.student_2.pk) == ["Physics"]


@pytest.mark.django_db
def test_student_filter_needs_batch_and_subject_on_one_row(school, institute_a) -> None:
    """Morning/Physics plus Evening/Math does not match a Morning/Math lecture."""
    mixed = student(institute_a, "mixed@example.com")
    link_student(
        mixed, {school.morning: [school.physics], school.evening: [school.math]}
    )
    add_lecture(school, title="Math")

    assert _list_titles(school.teacher_1.user, student_id=mixed.pk) == []


@pytest.mark.django_db
def test_list_is_scoped_to_the_user(school) -> None:
    add_lecture(school, title="Math")

    assert _list_titles(school.teacher_2.user) == []
    assert _list_titles(school.student_1.user) == ["Math"]


# Providers


def test_manual_link_provider_keeps_the_link_and_in_person_drops_it() -> None:
    manual = provider_for(DeliveryMode.MANUAL_LINK)
    in_person = provider_for(DeliveryMode.IN_PERSON)

    assert manual.create_meeting(None, f" {MEET_URL} ") == MEET_URL
    assert in_person.create_meeting(None, MEET_URL) == ""
    assert manual.cancel_meeting(None) is None
    assert manual.get_participants(None) == []
