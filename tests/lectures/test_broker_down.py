"""The broker is down when a schedule is saved (external audit, Phase 3).

Before the fix the save raised OperationalError after the commit: an error
page for a schedule that existed (a resubmit made a duplicate), and an edit
left its upcoming lectures missing until the nightly run.
"""

from __future__ import annotations

import logging

import pytest
from apps.lectures.models import RecurringSchedule
from apps.lectures.services import create_schedule, update_schedule
from django.urls import reverse

from tests.lectures.conftest import add_schedule, schedule_details, schedule_lectures
from tests.lectures.test_schedule_pages import _form, _preview_then_save
from tests.lectures.test_schedule_services import _in_context

DEAD_BROKER = "redis://127.0.0.1:1/0"  # nothing listens on port 1


@pytest.fixture
def broker_down(settings):
    """Real queueing against a broker that refuses the connection."""
    settings.CELERY_TASK_ALWAYS_EAGER = False
    settings.CELERY_BROKER_URL = DEAD_BROKER


@pytest.mark.django_db
def test_save_page_works_and_makes_the_lectures(
    broker_down, admin_client, school, django_capture_on_commit_callbacks, caplog
) -> None:
    with caplog.at_level(logging.WARNING, logger="apps.lectures.services"):
        response = _preview_then_save(
            admin_client,
            reverse("admin:lecture_schedule_create"),
            _form(school),
            capture=django_capture_on_commit_callbacks,
        )

    schedule = RecurringSchedule.unscoped.get()
    assert response.status_code == 200
    assert response.redirect_chain[-1][0] == reverse("admin:lecture_schedule_list")
    assert len(schedule_lectures(schedule)) == 7
    assert "Broker unavailable" in caplog.text


@pytest.mark.django_db
def test_edit_remakes_the_lectures_at_once(
    broker_down, school, django_capture_on_commit_callbacks
) -> None:
    schedule = add_schedule(school)

    with django_capture_on_commit_callbacks(execute=True):
        _in_context(
            school, update_schedule, schedule, schedule_details(school, title="New")
        )

    titles = {lecture.title for lecture in schedule_lectures(schedule)}
    assert titles == {"New"}
    assert len(schedule_lectures(schedule)) == 7


@pytest.mark.django_db
def test_when_making_them_fails_too_the_save_still_stands(
    broker_down, school, django_capture_on_commit_callbacks, caplog, monkeypatch
) -> None:
    def broken(*args, **kwargs):
        raise RuntimeError("database hiccup")

    monkeypatch.setattr("apps.lectures.tasks.generate_lectures", broken)

    with caplog.at_level(logging.ERROR, logger="apps.lectures.services"):
        with django_capture_on_commit_callbacks(execute=True):
            schedule = _in_context(
                school,
                create_schedule,
                school.morning.institute,
                schedule_details(school),
            )

    assert RecurringSchedule.unscoped.filter(pk=schedule.pk).exists()
    assert schedule_lectures(schedule) == []
    assert "the nightly job retries" in caplog.text
