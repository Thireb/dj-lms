"""Roadmap 7.6: the automatic defaulter rule (SPEC 6.2) and the Portal
access "Fee due" column (SPEC 3). Data from tests/finance/test_defaulters:
on 20 Oct student 1 owes 8,100 (since 10 Sep) and student 2 owes 800
(since 10 Oct); grace is 5 days."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from apps.core.tenancy import tenant_context
from apps.finance.access import apply_defaulter_rule
from apps.finance.models import Challan
from apps.finance.services import record_payment
from apps.finance.tasks import apply_all_defaulter_rules
from apps.notifications.models import Notification
from apps.people.models import PortalAccessRule
from apps.people.services import set_portal_blocked, set_portal_exempt
from django.urls import reverse

from tests.finance.test_defaulters import TODAY, owing  # noqa: F401
from tests.lectures.conftest import signed_in


@pytest.fixture
def rule_on(owing):  # noqa: F811
    settings = owing.morning.institute.settings
    settings.auto_block_defaulters = True
    settings.save()
    return owing


def _run(school, today=TODAY):
    institute = school.morning.institute
    with tenant_context(institute):
        return apply_defaulter_rule(institute, today)


def _rule(student):
    # unscoped: test assertion outside a tenant context.
    return PortalAccessRule.unscoped.filter(student=student).first()


def _blocked(*students):
    return [bool(_rule(s) and _rule(s).blocked) for s in students]


def _in_tenant(school, setter, student, **values):
    with tenant_context(school.morning.institute):
        setter(student, **values)


@pytest.mark.django_db
def test_off_by_default_does_nothing(owing) -> None:  # noqa: F811
    run = _run(owing)
    assert (run.blocked, run.unblocked) == (0, 0)
    assert _blocked(owing.student_1, owing.student_2) == [False, False]


@pytest.mark.django_db
def test_blocks_defaulters_once_and_tells_them(rule_on) -> None:
    run = _run(rule_on)
    assert (run.blocked, run.unblocked) == (2, 0)
    rule = _rule(rule_on.student_1)
    assert rule.blocked and rule.auto_blocked
    # unscoped: test assertion outside a tenant context.
    note = Notification.unscoped.get(user=rule_on.student_1.user, event="portal_access")
    assert "paused" in note.text
    assert (_run(rule_on).blocked, _run(rule_on).unblocked) == (0, 0)


@pytest.mark.django_db
def test_grace_days_count(rule_on) -> None:
    assert _run(rule_on, date(2026, 10, 15)).blocked == 1
    assert _blocked(rule_on.student_1, rule_on.student_2) == [True, False]


@pytest.mark.django_db
def test_exempt_students_are_never_auto_blocked(rule_on) -> None:
    _in_tenant(rule_on, set_portal_exempt, rule_on.student_2, exempt=True)
    _run(rule_on)
    assert _blocked(rule_on.student_1, rule_on.student_2) == [True, False]
    _in_tenant(rule_on, set_portal_exempt, rule_on.student_1, exempt=True)
    assert _run(rule_on).unblocked == 1  # exempt after the block: opened
    assert _blocked(rule_on.student_1) == [False]


@pytest.mark.django_db
def test_unblocks_once_nothing_is_overdue_beyond_grace(rule_on) -> None:
    _run(rule_on)
    with tenant_context(rule_on.morning.institute):
        bus = Challan.objects.get(student=rule_on.student_2)
        record_payment(
            bus, amount=Decimal("800"), paid_on=TODAY, method="cash", today=TODAY
        )
    run = _run(rule_on)
    assert (run.blocked, run.unblocked) == (0, 1)
    assert _blocked(rule_on.student_1, rule_on.student_2) == [True, False]
    rule = _rule(rule_on.student_2)
    assert not rule.auto_blocked
    # unscoped: test assertion outside a tenant context.
    texts = Notification.unscoped.filter(user=rule_on.student_2.user)
    assert "Your student portal is open again." in [n.text for n in texts]


@pytest.mark.django_db
def test_a_manual_block_is_never_undone(rule_on) -> None:
    _in_tenant(rule_on, set_portal_blocked, rule_on.student_new, blocked=True)
    _in_tenant(rule_on, set_portal_blocked, rule_on.student_2, blocked=True)
    _run(rule_on)
    assert not _rule(rule_on.student_2).auto_blocked  # already blocked by hand
    with tenant_context(rule_on.morning.institute):
        bus = Challan.objects.get(student=rule_on.student_2)
        record_payment(
            bus, amount=Decimal("800"), paid_on=TODAY, method="cash", today=TODAY
        )
    assert _run(rule_on).unblocked == 0
    assert _blocked(rule_on.student_new, rule_on.student_2) == [True, True]


@pytest.mark.django_db
def test_a_manual_unblock_lasts_until_the_next_run(rule_on) -> None:
    _run(rule_on)
    _in_tenant(rule_on, set_portal_blocked, rule_on.student_1, blocked=False)
    assert _blocked(rule_on.student_1) == [False]
    assert _run(rule_on).blocked == 1
    assert _rule(rule_on.student_1).auto_blocked


@pytest.mark.django_db
def test_other_institutes_are_not_touched(rule_on) -> None:
    _run(rule_on)
    assert _rule(rule_on.student_b) is None


@pytest.mark.django_db
def test_the_nightly_task(rule_on) -> None:
    """The challans are long overdue by the real date of any run."""
    assert apply_all_defaulter_rules() == 2
    assert apply_all_defaulter_rules() == 0


# Portal access page (SPEC 3: Fee due)


@pytest.mark.django_db
def test_portal_access_shows_fee_due_and_auto_blocks(rule_on, admin) -> None:
    _run(rule_on)
    _in_tenant(rule_on, set_portal_blocked, rule_on.student_new, blocked=True)
    html = signed_in(admin).get(reverse("admin:portal_access")).content.decode()
    assert "Fee due" in html and "Rs 8,100" in html and "Rs 800" in html
    assert html.count("Yes, auto") == 2


# Backlog P7-3 (owner decision 2026-10-17): switching the rule off opens
# the students it blocked; manual blocks stay.


@pytest.mark.django_db
def test_switching_the_rule_off_opens_its_blocks(rule_on, admin) -> None:
    from tests.institutes.test_settings_views import _settings_payload

    _run(rule_on)
    _in_tenant(rule_on, set_portal_blocked, rule_on.student_new, blocked=True)
    client = signed_in(admin)
    url = reverse("admin:institute_settings")
    response = client.post(url, _settings_payload(auto_block_defaulters="on"))
    assert response.status_code == 302
    assert _blocked(rule_on.student_1, rule_on.student_2) == [True, True]
    response = client.post(url, _settings_payload(), follow=True)
    html = response.content.decode()
    assert "Auto-block is off: 2 students blocked by it can use" in html
    assert _blocked(rule_on.student_1, rule_on.student_2) == [False, False]
    assert _blocked(rule_on.student_new) == [True]  # the manual block stays
    assert not _rule(rule_on.student_1).auto_blocked


@pytest.mark.django_db
def test_saving_with_the_rule_off_changes_nothing(owing, admin) -> None:  # noqa: F811
    from tests.institutes.test_settings_views import _settings_payload

    _in_tenant(owing, set_portal_blocked, owing.student_1, blocked=True)
    signed_in(admin).post(reverse("admin:institute_settings"), _settings_payload())
    assert _blocked(owing.student_1) == [True]
