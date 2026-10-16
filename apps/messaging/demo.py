"""Demo messages for seed_demo (roadmap 6.3, SPEC 10: "30 messages across
roles"). Fake names and text only. A second run adds nothing."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.utils import timezone

from apps.accounts.models import User
from apps.core.roles import Role
from apps.core.tenancy import tenant_context
from apps.institutes.models import Institute
from apps.messaging.models import Audience, Broadcast, Draft, Thread
from apps.messaging.services import (
    reachable,
    reply,
    save_draft,
    send_broadcast,
    send_message,
)
from apps.people.demo import (
    DEMO_GUARDIAN_EMAIL,
    DEMO_STUDENT_EMAIL,
    DEMO_TEACHER_EMAIL,
)

DEMO_ADMIN_EMAIL = "demo-admin@example.com"

# (from, to, subject, [first message, reply, reply, ...]); "from" and "to"
# name a demo user or "<role>" for another reachable person of that role.
CONVERSATIONS = [
    (
        "student",
        "teacher",
        "Question about the homework",
        [
            "Is question 4 about speed or velocity?",
            "Velocity. Show the direction in your answer.",
            "Thank you, I will add it.",
        ],
    ),
    (
        "guardian",
        "teacher",
        "Absence on Monday",
        [
            "My child has a doctor's visit on Monday morning and will miss class.",
            "Thank you for telling me. I will share the notes after class.",
        ],
    ),
    (
        "admin",
        "teacher",
        "Timetable for next week",
        [
            "Please check the new timetable before Friday.",
            "Checked. The Wednesday class can move to 4 PM.",
            "Done. The schedule is updated.",
        ],
    ),
    (
        "teacher",
        "guardian",
        "Progress this month",
        [
            "Your child did well in the unit test. Practice graphs at home.",
            "Thank you. We will practice every evening.",
        ],
    ),
    (
        "teacher",
        "student",
        "Good work on the test",
        [
            "Your answer on forces was the clearest in the class.",
        ],
    ),
    (
        "student",
        "admin",
        "Fee receipt",
        [
            "I paid the fee at the bank. Where do I send the receipt?",
            "Give it to the office or upload it when Fee Pay opens.",
        ],
    ),
    (
        "admin",
        "guardian",
        "Parent meeting",
        [
            "The parent meeting is on Saturday at 11 AM.",
            "We will come. Thank you.",
        ],
    ),
    (
        "teacher",
        "<teacher>",
        "Shared test paper",
        [
            "Can we use the same test paper for both batches?",
            "Yes, but change the last two questions.",
        ],
    ),
    (
        "<student>",
        "teacher",
        "Lecture link",
        [
            "The meeting link did not open for me today.",
            "Try again from My lectures. It opens when I start the class.",
        ],
    ),
    (
        "<guardian>",
        "teacher",
        "Homework load",
        [
            "Is the weekend homework due on Monday?",
            "Yes, on Monday before class.",
        ],
    ),
    (
        "admin",
        "<teacher>",
        "Lab equipment",
        [
            "The new lab kits arrive on Thursday.",
            "Thank you. I will plan a practical class.",
        ],
    ),
    (
        "teacher",
        "<student>",
        "Missing answer",
        [
            "Your answer for the chapter questions is missing.",
            "Sorry, I will send it today.",
        ],
    ),
]


def _people(institute: Institute) -> dict[str, Any]:
    by_email = {
        user.email: user
        for user in User.objects.filter(
            email__in=[
                DEMO_ADMIN_EMAIL,
                DEMO_TEACHER_EMAIL,
                DEMO_STUDENT_EMAIL,
                DEMO_GUARDIAN_EMAIL,
            ]
        )
    }
    return {
        "admin": by_email.get(DEMO_ADMIN_EMAIL),
        "teacher": by_email.get(DEMO_TEACHER_EMAIL),
        "student": by_email.get(DEMO_STUDENT_EMAIL),
        "guardian": by_email.get(DEMO_GUARDIAN_EMAIL),
    }


def _other(people: dict[str, Any], wanted: str, partner: Any) -> Any:
    """Another person of ``wanted`` role whom ``partner`` can reach."""
    role = {"<teacher>": Role.TEACHER, "<student>": Role.STUDENT}.get(
        wanted, Role.GUARDIAN
    )
    known = {user.pk for user in people.values() if user is not None}
    return (
        reachable(partner)
        .filter(role=role)
        .exclude(pk__in=known)
        .order_by("pk")
        .first()
    )


def seed_messages(institute: Institute) -> None:
    """About 30 messages across roles, one broadcast to the teachers and
    one draft. Runs once."""
    with tenant_context(institute):
        people = _people(institute)
        if None in people.values() or Thread.objects.exists():
            return
        start = timezone.now() - timedelta(days=6)
        for number, (sender_key, to_key, subject, texts) in enumerate(CONVERSATIONS):
            sender = people.get(sender_key) or _other(
                people, sender_key, people[to_key]
            )
            recipient = people.get(to_key) or _other(people, to_key, sender)
            if sender is None or recipient is None:
                continue
            at = start + timedelta(hours=11 * number)
            thread = send_message(sender, recipient, subject, texts[0], now=at)
            for step, text in enumerate(texts[1:], start=1):
                author = recipient if step % 2 else sender
                reply(thread, author, text, now=at + timedelta(minutes=40 * step))
        send_broadcast(
            people["admin"],
            Audience.TEACHERS,
            "Staff meeting on Friday",
            "All teachers: staff meeting on Friday at 2 PM in the main hall.",
            now=start + timedelta(days=5),
        )
        save_draft(
            people["teacher"],
            recipient=people["admin"],
            subject="Leave next month",
            body="I would like to ask for two days of leave in",
        )


def reset_messages(institute: Institute) -> int:
    """Delete the institute's messages. Uses ``unscoped`` on purpose: a
    management command, one institute."""
    deleted = 0
    for model in (Draft, Thread, Broadcast):
        count, _ = model.unscoped.filter(institute=institute).delete()
        deleted += count
    return deleted
