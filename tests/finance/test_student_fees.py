"""Roadmap 7.1 part 2: fee plans and discounts on Enrol and Edit (SPEC 4.1),
and the Monthly fee column on All Students (SPEC 3)."""

from __future__ import annotations

import re
from decimal import Decimal

import pytest
from apps.core.tenancy import tenant_context
from apps.finance.models import StudentFeePlan
from apps.finance.services import FeeChoice, set_student_fee_plans
from apps.people.models import StudentProfile
from django.core.exceptions import ValidationError
from django.urls import reverse

from tests.finance.conftest import add_plan, give_plan
from tests.lectures.conftest import signed_in
from tests.people.test_student_pages import _form

ENROL = reverse("admin:student_create")
LIST = reverse("admin:student_list")


def _rows(student) -> list[tuple[str, str, Decimal]]:
    # unscoped: test assertion outside a tenant context.
    rows = StudentFeePlan.unscoped.filter(student=student).order_by("fee_plan__name")
    return [(row.fee_plan.name, row.discount_type, row.discount) for row in rows]


@pytest.mark.django_db
def test_enrol_with_fee_plans_and_a_discount(fees_school, admin) -> None:
    tuition = add_plan(fees_school)
    add_plan(fees_school, "Lab", "1000")
    client = signed_in(admin)
    html = client.get(ENROL).content.decode()
    assert f'name="fee_{tuition.pk}"' in html and "Tuition: 4,500.00 a month" in html
    data = _form(
        fees_school,
        **{
            f"fee_{tuition.pk}": "on",
            f"fee_{tuition.pk}_type": "percent",
            f"fee_{tuition.pk}_discount": "10",
        },
    )
    assert client.post(ENROL, data).status_code == 302
    student = StudentProfile.unscoped.get(user__email="alex@example.com")
    assert _rows(student) == [("Tuition", "percent", Decimal("10.00"))]
    html = client.get(LIST).content.decode()
    assert "Monthly fee" in html and "Rs 4,050" in html


@pytest.mark.django_db
def test_enrol_needs_a_fee_plan_and_valid_discounts(fees_school, admin) -> None:
    tuition = add_plan(fees_school)
    client = signed_in(admin)
    html = client.post(ENROL, _form(fees_school)).content.decode()
    assert "Choose at least one fee plan." in html
    data = _form(
        fees_school,
        **{
            f"fee_{tuition.pk}": "on",
            f"fee_{tuition.pk}_type": "percent",
            f"fee_{tuition.pk}_discount": "150",
        },
    )
    html = client.post(ENROL, data).content.decode()
    assert "A percent discount is 0 to 100." in html
    assert not StudentProfile.unscoped.filter(user__email="alex@example.com").exists()


@pytest.mark.django_db
def test_edit_shows_and_changes_the_plans(fees_school, admin) -> None:
    student = fees_school.student_1
    tuition, lab = add_plan(fees_school), add_plan(fees_school, "Lab", "1000")
    give_plan(student, tuition, "amount", "500")
    edit = reverse("admin:student_edit", kwargs={"pk": student.pk})
    client = signed_in(admin)
    html = client.get(edit).content.decode()
    tag = re.search(rf'<input[^>]*name="fee_{tuition.pk}"[^>]*>', html).group(0)
    assert "checked" in tag
    lab_tag = re.search(rf'<input[^>]*name="fee_{lab.pk}"[^>]*>', html).group(0)
    assert "checked" not in lab_tag
    assert 'value="500' in html
    data = {
        "full_name": "Ali Student",
        "guardian_phone": "0300-1111111",
        "email": student.user.email,
        "batch_subjects": [f"{fees_school.morning.pk}:{fees_school.math.pk}"],
        f"fee_{lab.pk}": "on",
        f"fee_{lab.pk}_type": "none",
    }
    assert client.post(edit, data).status_code == 302
    assert _rows(student) == [("Lab", "none", Decimal("0.00"))]


@pytest.mark.django_db
def test_an_inactive_plan_stays_only_where_it_is(fees_school) -> None:
    student, other = fees_school.student_1, fees_school.student_2
    old = add_plan(fees_school, "Old fee", "300")
    give_plan(student, old)
    old.is_active = False
    old.save()
    with tenant_context(student.institute):
        set_student_fee_plans(student, [FeeChoice(old)])  # kept
        with pytest.raises(ValidationError, match="Old fee is inactive."):
            set_student_fee_plans(other, [FeeChoice(old)])
        with pytest.raises(ValidationError, match="An amount discount is 0 to 300"):
            set_student_fee_plans(student, [FeeChoice(old, "amount", Decimal("301"))])
    assert _rows(student) == [("Old fee", "none", Decimal("0.00"))]


@pytest.mark.django_db
def test_basic_institutes_have_no_fee_fields(school) -> None:
    from apps.core.roles import Role

    from tests.conftest import make_user

    admin = make_user(
        email="a@example.com",
        role=Role.INSTITUTE_ADMIN,
        institute=school.morning.institute,
    )
    client = signed_in(admin)
    html = client.get(ENROL).content.decode()
    assert (
        'name="fee_' not in html
        and "Monthly fee" not in client.get(LIST).content.decode()
    )
