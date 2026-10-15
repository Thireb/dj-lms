"""Assignment and submission rows: creation, tenant isolation and
``for_user`` scopes (AGENTS.md section 7)."""

from __future__ import annotations

import pytest
from apps.assessments.models import Assignment, Submission
from apps.core.roles import Role
from apps.core.tenancy import tenant_context
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from tests.assessments.conftest import add_assignment, answer, in_days
from tests.conftest import make_user
from tests.school import link_guardian, link_teacher


def _visible(model, user) -> set[int]:
    with tenant_context(user.institute):
        return set(model.objects.for_user(user).values_list("pk", flat=True))


@pytest.mark.django_db
def test_create_and_answer(school) -> None:
    assignment = add_assignment(school)
    row = answer(assignment, school.student_1)
    assert assignment.total_marks == 10
    assert row.marks is None and not row.is_graded
    assert row.submitted_at is not None


@pytest.mark.django_db
def test_one_answer_per_student(school) -> None:
    assignment = add_assignment(school)
    answer(assignment, school.student_1)
    with pytest.raises(IntegrityError), transaction.atomic():
        with tenant_context(assignment.institute):
            Submission.objects.create(
                institute=assignment.institute,
                assignment=assignment,
                student=school.student_1,
                answer="Second",
                submitted_at=timezone.now(),
            )


@pytest.mark.django_db
def test_rows_of_another_institute_are_refused(school) -> None:
    assignment = add_assignment(school)
    with pytest.raises(ValidationError), tenant_context(assignment.institute):
        Submission.objects.create(
            institute=assignment.institute,
            assignment=assignment,
            student=school.student_b,
            answer="Wrong school",
            submitted_at=timezone.now(),
        )
    with pytest.raises(ValidationError), tenant_context(assignment.institute):
        Assignment.objects.create(
            institute=assignment.institute,
            title="Wrong batch",
            instructions="-",
            teacher=school.teacher_1,
            batch=school.batch_b,
            subject=school.math,
            total_marks=5,
            due_at=in_days(1),
        )


@pytest.mark.django_db
def test_marks_cannot_pass_the_total(school) -> None:
    row = answer(add_assignment(school, total_marks=5), school.student_1)
    row.marks = 6
    with pytest.raises(ValidationError), tenant_context(row.institute):
        row.save()


@pytest.mark.django_db
def test_no_context_and_anonymous_see_nothing(school, anonymous_user) -> None:
    answer(add_assignment(school), school.student_1)
    for model in (Assignment, Submission):
        assert not model.objects.exists()
        assert not model.objects.for_user(anonymous_user).exists()
        assert not model.objects.for_user(None).exists()


@pytest.mark.django_db
def test_admin_sees_only_own_institute(school, institute_a, institute_b) -> None:
    mine = add_assignment(school)
    answer(mine, school.student_1)
    admin_a = make_user(
        email="admin-a@example.com", role=Role.INSTITUTE_ADMIN, institute=institute_a
    )
    admin_b = make_user(
        email="admin-b@example.com", role=Role.INSTITUTE_ADMIN, institute=institute_b
    )
    assert _visible(Assignment, admin_a) == {mine.pk}
    assert _visible(Assignment, admin_b) == set()
    assert len(_visible(Submission, admin_a)) == 1
    assert _visible(Submission, admin_b) == set()


@pytest.mark.django_db
def test_teacher_sees_only_own(school) -> None:
    mine = add_assignment(school)
    theirs = add_assignment(
        school,
        title="Waves",
        teacher=school.teacher_2,
        batch=school.evening,
        subject=school.physics,
    )
    answer(mine, school.student_1)
    answer(theirs, school.student_2)
    assert _visible(Assignment, school.teacher_1.user) == {mine.pk}
    assert _visible(Assignment, school.teacher_2.user) == {theirs.pk}
    # unscoped: test assertion outside a tenant context.
    own = Submission.unscoped.get(assignment=mine)
    assert _visible(Submission, school.teacher_1.user) == {own.pk}


@pytest.mark.django_db
def test_student_and_guardian_see_their_batch_and_subject(school) -> None:
    math = add_assignment(school)
    physics = add_assignment(
        school,
        title="Waves",
        teacher=school.teacher_2,
        batch=school.evening,
        subject=school.physics,
    )
    assert _visible(Assignment, school.student_1.user) == {math.pk}
    assert _visible(Assignment, school.student_2.user) == {physics.pk}
    assert _visible(Assignment, school.guardian_1.user) == {math.pk}
    assert _visible(Assignment, school.guardian_2.user) == {physics.pk}
    assert _visible(Assignment, school.student_new.user) == set()


@pytest.mark.django_db
def test_enrolment_must_have_both_batch_and_subject(school) -> None:
    """student_1 is in Morning (Math, Physics) and student_2 takes Physics
    in Evening: an Evening Math assignment is for neither."""
    link_teacher(school.teacher_2, {school.evening: [school.physics, school.math]})
    evening_math = add_assignment(
        school, teacher=school.teacher_2, batch=school.evening, subject=school.math
    )
    assert evening_math.pk not in _visible(Assignment, school.student_1.user)
    assert evening_math.pk not in _visible(Assignment, school.student_2.user)


@pytest.mark.django_db
def test_answers_are_private(school) -> None:
    assignment = add_assignment(school, batch=school.morning)
    own = answer(assignment, school.student_1)
    other_guardian = link_guardian(school.student_2, "g9-a@example.com")
    assert _visible(Submission, school.student_1.user) == {own.pk}
    assert _visible(Submission, school.student_2.user) == set()
    assert _visible(Submission, school.guardian_1.user) == {own.pk}
    assert _visible(Submission, other_guardian.user) == set()
    assert _visible(Submission, school.teacher_2.user) == set()
