"""Roadmap 7.2 part 2: the challan PDF (SPEC 9.1)."""

from __future__ import annotations

import re
import zlib
from datetime import timedelta
from decimal import Decimal

import pytest
from apps.core.tenancy import tenant_context
from apps.finance.models import Challan
from apps.finance.pdf import challan_html
from apps.finance.services import cancel_challan, generate_challans
from django.urls import reverse
from django.utils import timezone

from tests.finance.conftest import add_plan, give_plan
from tests.lectures.conftest import signed_in


def _pages(pdf: bytes) -> int:
    """Count the page objects, also inside compressed object streams."""
    text = pdf
    # Keep the end-of-line bytes: the compressed data can end with b"\r".
    # decompressobj leaves anything after the zlib stream unused.
    for stream in re.findall(rb"stream\r?\n(.*?)endstream", pdf, re.S):
        try:
            text += zlib.decompressobj().decompress(stream)
        except zlib.error:
            continue
    return len(re.findall(rb"/Type\s*/Page\b", text))


@pytest.fixture
def challans(fees_school):
    """Student 1: Tuition 4,500 less 10% and Lab 1,000; student 2: Bus 800.
    One challan each for this month, and one for student 1 last month."""
    school = fees_school
    give_plan(school.student_1, add_plan(school), "percent", "10")
    give_plan(school.student_1, add_plan(school, "Lab", "1000"))
    give_plan(school.student_2, add_plan(school, "Bus", "800"))
    institute = school.morning.institute
    today = timezone.localdate()
    month = today.replace(day=1)
    earlier = (month - timedelta(days=1)).replace(day=1)
    with tenant_context(institute):
        old = generate_challans(
            institute, earlier, today + timedelta(days=2), [school.student_1]
        )
        rows = generate_challans(
            institute,
            month,
            today + timedelta(days=5),
            [school.student_1, school.student_2],
        )
    return old + rows


@pytest.mark.django_db
def test_the_challan_html(fees_school, challans) -> None:
    institute = fees_school.morning.institute
    institute.settings.late_fee = Decimal("250")
    institute.settings.save()
    _old, mine, _other = challans
    with tenant_context(institute):
        html = challan_html([mine], institute)
    assert html.count("Fee Challan") == 3
    for copy in ("Institute copy", "Student copy", "Bank / office copy"):
        assert copy in html
    assert mine.number in html and "Rs 4,500" in html and "Rs 450" in html
    assert "Total payable" in html and "Rs 5,050" in html
    assert "Five thousand fifty rupees only" in html
    assert "Previous balance (not included above): Rs 5,050" in html
    assert fees_school.guardian_1.user.email in html  # no name: the email
    assert "A late fee of Rs 250 is added" in html
    assert "#" not in re.sub(r"&#\d+;", "", html.split("</style>")[1])  # no raw colours


@pytest.mark.django_db
def test_text_in_the_pdf_html_is_escaped(fees_school, challans) -> None:
    user = fees_school.student_1.user
    user.first_name = "<b>Bilal"
    user.save()
    institute = fees_school.morning.institute
    with tenant_context(institute):
        html = challan_html([challans[1]], institute)
    assert "&lt;b&gt;Bilal" in html and "<b>Bilal" not in html


@pytest.mark.django_db
def test_one_challan_pdf(fees_school, admin, challans) -> None:
    mine = challans[1]
    response = signed_in(admin).get(
        reverse("admin:challan_pdf", kwargs={"pk": mine.pk})
    )
    assert response["Content-Type"] == "application/pdf"
    assert f'filename="{mine.number}.pdf"' in response["Content-Disposition"]
    assert response.content.startswith(b"%PDF") and _pages(response.content) == 1


@pytest.mark.django_db
def test_bulk_print_follows_the_filters(fees_school, admin, challans) -> None:
    client = signed_in(admin)
    url = reverse("admin:challan_print")
    assert _pages(client.get(url).content) == 3
    month = timezone.localdate()
    assert _pages(client.get(url, {"month": f"{month:%Y-%m}"}).content) == 2
    with tenant_context(admin.institute):
        cancel_challan(challans[2])
    assert _pages(client.get(url, {"month": f"{month:%Y-%m}"}).content) == 1
    response = client.get(url, {"q": "nobody"})
    assert response.status_code == 302


@pytest.mark.django_db
def test_students_cannot_print_through_the_admin(fees_school, challans) -> None:
    mine = challans[1]
    url = reverse("admin:challan_pdf", kwargs={"pk": mine.pk})
    assert signed_in(fees_school.student_1.user).get(url).status_code == 403
    Challan.unscoped.filter(pk=mine.pk).update(
        institute=fees_school.teacher_b.institute
    )
    from apps.core.roles import Role

    from tests.conftest import make_user

    other = make_user(
        email="b@example.com",
        role=Role.INSTITUTE_ADMIN,
        institute=fees_school.morning.institute,
    )
    assert signed_in(other).get(url).status_code == 404
