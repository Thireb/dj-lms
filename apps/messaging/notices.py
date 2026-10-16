"""New-message notifications (roadmap 6.3, SPEC 7 "New message":
recipient). The link opens the thread in the recipient's own portal."""

from __future__ import annotations

from typing import Any

from django.urls import reverse

from apps.messaging.models import Thread
from apps.notifications.services import notify
from apps.ui.menus.registry import portal_for_user


def person(user: Any) -> str:
    return user.get_full_name() or user.email


def thread_url(user: Any, thread: Thread) -> str:
    portal = portal_for_user(user)
    if portal is None:
        return ""
    return reverse(f"{portal}:message_thread", kwargs={"pk": thread.pk})


def new_message(thread: Thread, sender: Any, recipients: list[Any]) -> None:
    text = f"New message from {person(sender)}: {thread.subject}"
    for user in recipients:
        notify([user], "new_message", text, thread_url(user, thread))


def broadcast_sent(broadcast: Any, threads: dict[Any, Thread]) -> None:
    """One notification per recipient, each linking to their own thread."""
    text = f"New message from {person(broadcast.sender)}: {broadcast.subject}"
    notify(
        list(threads), "new_message", text, lambda user: thread_url(user, threads[user])
    )
