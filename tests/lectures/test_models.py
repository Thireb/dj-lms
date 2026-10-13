"""Lecture model and for_user scopes (roadmap 3.1, AGENTS.md section 7)."""

from __future__ import annotations

from datetime import timedelta

import pytest
from apps.academics.models import Batch, TeacherBatchSubject
from apps.core.tenancy import tenant_context
from apps.lectures.models import DeliveryMode, Lecture
from django.core.exceptions import ValidationError

from tests.conftest import FakeUser
from tests.lectures.conftest import MEET_URL, add_lecture, soon
from tests.people.conftest import student
from tests.school import link_guardian, link_student


def _titles(user) -> set[str]:
    return set(Lecture.objects.for_user(user).values_list("title", flat=True))


@pytest.mark.django_db
def test_create_stores_utc_and_end_time(school) -> None:
    lecture = add_lecture(school, duration_minutes=90)

    assert lecture.starts_at.utcoffset() == timedelta(0)
    assert lecture.ends_at == lecture.starts_at + timedelta(minutes=90)
    assert lecture.status == "scheduled"
    assert str(lecture) == "Algebra basics"


@pytest.mark.django_db
def test_no_tenant_context_and_anonymous_see_nothing(school, anonymous_user) -> None:
    add_lecture(school)

    assert Lecture.objects.count() == 0
    assert Lecture.objects.for_user(anonymous_user).count() == 0
    with tenant_context(school.morning.institute):
        assert Lecture.objects.count() == 1


@pytest.mark.django_db
def test_admin_sees_own_institute_only(school, admin_a, admin_b) -> None:
    add_lecture(school)

    assert _titles(admin_a) == {"Algebra basics"}
    assert _titles(admin_b) == set()


@pytest.mark.django_db
def test_teacher_sees_own_lectures_only(school) -> None:
    add_lecture(school, title="Teacher 1 lecture")
    add_lecture(
        school,
        title="Teacher 2 lecture",
        teacher=school.teacher_2,
        batch=school.evening,
        subjects=[school.physics],
    )

    assert _titles(school.teacher_1.user) == {"Teacher 1 lecture"}
    assert _titles(school.teacher_2.user) == {"Teacher 2 lecture"}
    assert _titles(school.teacher_idle.user) == set()
    assert _titles(school.teacher_b.user) == set()


@pytest.mark.django_db
def test_student_and_guardian_see_lectures_of_their_batch_and_subject(school) -> None:
    add_lecture(school, title="Morning math")
    add_lecture(
        school,
        title="Evening physics",
        teacher=school.teacher_2,
        batch=school.evening,
        subjects=[school.physics],
    )

    assert _titles(school.student_1.user) == {"Morning math"}
    assert _titles(school.guardian_1.user) == {"Morning math"}
    assert _titles(school.student_2.user) == {"Evening physics"}
    assert _titles(school.guardian_2.user) == {"Evening physics"}
    assert _titles(school.student_new.user) == set()
    assert _titles(school.student_b.user) == set()


@pytest.mark.django_db
def test_enrolment_must_match_batch_and_subject_on_one_row(school, institute_a) -> None:
    """Morning/Physics plus Evening/Math does not show a Morning/Math lecture."""
    mixed = student(institute_a, "mixed@example.com")
    link_student(
        mixed, {school.morning: [school.physics], school.evening: [school.math]}
    )
    guardian = link_guardian(mixed, "mixed-g@example.com")
    add_lecture(school, title="Morning math")

    assert _titles(mixed.user) == set()
    assert _titles(guardian.user) == set()


@pytest.mark.django_db
def test_lecture_with_two_subjects_shows_once(school) -> None:
    with tenant_context(school.morning.institute):
        TeacherBatchSubject.objects.create(
            institute=school.morning.institute,
            teacher=school.teacher_1,
            batch=school.morning,
            subject=school.physics,
        )
    add_lecture(school, subjects=[school.math, school.physics])

    # student_1 takes both subjects in Morning: one row, not two.
    assert Lecture.objects.for_user(school.student_1.user).count() == 1


@pytest.mark.django_db
def test_super_admin_sees_all_and_unknown_role_sees_nothing(
    school, super_admin_user, institute_a
) -> None:
    add_lecture(school)

    assert _titles(super_admin_user) == {"Algebra basics"}
    assert _titles(FakeUser(role="accountant", institute=institute_a)) == set()


@pytest.mark.django_db
def test_clean_rejects_other_institute_batch(school, institute_b) -> None:
    (other_batch,) = Batch.unscoped.filter(institute=institute_b)
    lecture = Lecture(
        institute=school.morning.institute,
        title="Mixed",
        teacher=school.teacher_1,
        batch=other_batch,
        starts_at=soon(),
        duration_minutes=60,
        meeting_url=MEET_URL,
    )

    with pytest.raises(ValidationError, match="same institute"):
        lecture.full_clean()


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("mode", "link", "message"),
    [
        (DeliveryMode.MANUAL_LINK, "", "Paste the meeting link"),
        (DeliveryMode.IN_PERSON, MEET_URL, "has no meeting link"),
        (DeliveryMode.MANUAL_LINK, "ftp://files.example.com/x", "valid URL"),
    ],
)
def test_clean_checks_the_meeting_link(school, mode, link, message) -> None:
    lecture = Lecture(
        institute=school.morning.institute,
        title="Link check",
        teacher=school.teacher_1,
        batch=school.morning,
        starts_at=soon(),
        duration_minutes=60,
        delivery_mode=mode,
        meeting_url=link,
    )

    with pytest.raises(ValidationError, match=message):
        lecture.save()


@pytest.mark.django_db
@pytest.mark.parametrize("minutes", [9, 481])
def test_duration_limits(school, minutes) -> None:
    lecture = Lecture(
        institute=school.morning.institute,
        title="Too short or long",
        teacher=school.teacher_1,
        batch=school.morning,
        starts_at=soon(),
        duration_minutes=minutes,
        meeting_url=MEET_URL,
    )

    with pytest.raises(ValidationError, match="duration_minutes"):
        lecture.save()
