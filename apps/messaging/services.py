"""Messaging rules (roadmap 6.3, FEATURES 11, SPEC 4.19 and 6.5).

Who can message whom (SPEC 6.5):
- Admin and sub-admin: anyone in the institute.
- Teacher: admins, other teachers, students in their batches and the
  guardians of those students.
- Student: admins and the teachers of their batches.
- Guardian: admins and the teachers of their children's batches.

Only active users take part. A reply goes to everyone in the thread who is
still active. Every function runs in the institute's tenant context.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Exists, OuterRef, Q, QuerySet, Subquery, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.academics.models import StudentBatchSubject, TeacherBatchSubject
from apps.accounts.models import User
from apps.core.roles import Role
from apps.core.tenancy import require_tenant_context
from apps.messaging.models import (
    MAX_BODY,
    MAX_SUBJECT,
    Draft,
    Message,
    Thread,
    ThreadMember,
)
from apps.people.models import GuardianStudentLink, ProfileStatus

NO_SUBJECT = "(No subject)"
ADMIN_ROLES = (Role.INSTITUTE_ADMIN, Role.SUB_ADMIN)
NOT_REACHABLE = "You cannot send a message to this person."
NOT_A_MEMBER = "You are not in this conversation."
NO_ONE_ACTIVE = "No one else in this conversation can get messages now."
FOLDERS = ("inbox", "sent", "starred", "trash")
NEVER = datetime(2000, 1, 1, tzinfo=UTC)  # "never read": before any message


# Reach (SPEC 6.5)


def reachable(user: Any) -> QuerySet[User]:
    """The active users of the institute that ``user`` may start a thread
    with."""
    base = User.objects.filter(institute_id=user.institute_id, is_active=True).exclude(
        pk=user.pk
    )
    role = user.role
    if role in ADMIN_ROLES:
        return base
    admins = Q(role__in=ADMIN_ROLES)
    if role == Role.TEACHER:
        batches = TeacherBatchSubject.objects.filter(teacher__user=user).values(
            "batch_id"
        )
        students = StudentBatchSubject.objects.filter(
            batch_id__in=batches, student__status=ProfileStatus.ACTIVE
        ).values("student_id")
        return base.filter(
            admins
            | Q(role=Role.TEACHER)
            | Q(role=Role.STUDENT, student_profile__in=students)
            | Q(
                role=Role.GUARDIAN,
                guardian_profile__student_links__student__in=students,
            )
        ).distinct()
    if role == Role.STUDENT:
        batches = StudentBatchSubject.objects.filter(student__user=user).values(
            "batch_id"
        )
    elif role == Role.GUARDIAN:
        children = GuardianStudentLink.objects.filter(guardian__user=user).values(
            "student_id"
        )
        batches = StudentBatchSubject.objects.filter(
            student_id__in=children, student__status=ProfileStatus.ACTIVE
        ).values("batch_id")
    else:
        return base.none()
    teachers = TeacherBatchSubject.objects.filter(batch_id__in=batches).values(
        "teacher_id"
    )
    return base.filter(
        admins | Q(role=Role.TEACHER, teacher_profile__in=teachers)
    ).distinct()


def can_message(sender: Any, recipient: Any) -> bool:
    return reachable(sender).filter(pk=getattr(recipient, "pk", None)).exists()


def search_people(user: Any, query: str, limit: int = 20) -> list[User]:
    """The reachable people whose name or email has ``query`` (compose)."""
    rows = reachable(user)
    for word in query.split()[:3]:
        rows = rows.filter(
            Q(first_name__icontains=word)
            | Q(last_name__icontains=word)
            | Q(email__icontains=word)
        )
    return list(rows.order_by("first_name", "last_name", "pk")[:limit])


# Sending


def _clean(subject: str, body: str, errors: dict[str, str]) -> tuple[str, str]:
    subject, body = subject.strip(), body.strip()
    if not body:
        errors["body"] = "Write your message."
    elif len(body) > MAX_BODY:
        errors["body"] = f"A message can have {MAX_BODY} characters at most."
    if len(subject) > MAX_SUBJECT:
        errors["subject"] = f"A subject can have {MAX_SUBJECT} characters at most."
    return subject, body


def _start_thread(
    sender: Any,
    recipient: Any,
    subject: str,
    body: str,
    now: datetime,
    broadcast: Any = None,
) -> Thread:
    thread = Thread.objects.create(
        institute_id=sender.institute_id,
        subject=subject or NO_SUBJECT,
        broadcast=broadcast,
        created_at=now,
        last_message_at=now,
    )
    ThreadMember.objects.bulk_create(
        [
            ThreadMember(
                institute_id=sender.institute_id,
                thread=thread,
                user=sender,
                last_read_at=now,
            ),
            ThreadMember(
                institute_id=sender.institute_id, thread=thread, user=recipient
            ),
        ]
    )
    Message.objects.create(
        institute_id=sender.institute_id,
        thread=thread,
        sender=sender,
        body=body,
        created_at=now,
    )
    return thread


@transaction.atomic
def send_message(
    sender: Any,
    recipient: Any,
    subject: str,
    body: str,
    *,
    now: datetime | None = None,
) -> Thread:
    """A new thread between the sender and one recipient (SPEC 4.19)."""
    require_tenant_context(sender.institute)
    errors: dict[str, str] = {}
    subject, body = _clean(subject, body, errors)
    if recipient is None or not can_message(sender, recipient):
        errors["recipient"] = NOT_REACHABLE
    if errors:
        raise ValidationError(errors)
    return _start_thread(sender, recipient, subject, body, now or timezone.now())


@transaction.atomic
def reply(
    thread: Thread, sender: Any, body: str, *, now: datetime | None = None
) -> Message:
    """Add a message to the thread. It comes back out of the trash for
    everyone in it, like a new email."""
    require_tenant_context(thread.institute)
    now = now or timezone.now()
    member = ThreadMember.objects.filter(thread=thread, user=sender).first()
    if member is None:
        raise ValidationError(NOT_A_MEMBER)
    errors: dict[str, str] = {}
    _, body = _clean("", body, errors)
    if errors:
        raise ValidationError(errors)
    locked = Thread.objects.select_for_update().get(pk=thread.pk)
    others = locked.members.exclude(user=sender)
    if not others.filter(user__is_active=True).exists():
        raise ValidationError(NO_ONE_ACTIVE)
    message = Message.objects.create(
        institute_id=locked.institute_id,
        thread=locked,
        sender=sender,
        body=body,
        created_at=now,
    )
    locked.last_message_at = now
    locked.save(update_fields=["last_message_at"])
    others.update(trashed_at=None, deleted=False)
    member.last_read_at = now
    member.trashed_at = None
    member.deleted = False
    member.save(update_fields=["last_read_at", "trashed_at", "deleted"])
    return message


# Folders (FEATURES 11: Inbox, Sent, Starred, Drafts, Trash)


@dataclass(frozen=True)
class ThreadRow:
    thread: Thread
    member: ThreadMember
    last_body: str
    unread: bool
    people: str  # the others in the thread


def _from_others(user: Any) -> Any:
    return Message.objects.filter(thread=OuterRef("thread")).exclude(sender=user)


def folder_members(user: Any, folder: str) -> QuerySet[ThreadMember]:
    """The user's thread rows in one folder, newest first."""
    if folder not in FOLDERS:
        raise ValueError(f"Unknown folder: {folder!r}")
    rows = ThreadMember.objects.for_user(user).filter(deleted=False)
    if folder == "trash":
        rows = rows.filter(trashed_at__isnull=False)
    else:
        rows = rows.filter(trashed_at__isnull=True)
    if folder == "inbox":
        rows = rows.filter(Exists(_from_others(user)))
    elif folder == "sent":
        mine = Message.objects.filter(thread=OuterRef("thread"), sender=user)
        rows = rows.filter(Exists(mine)).exclude(thread__broadcast__sender=user)
    elif folder == "starred":
        rows = rows.filter(starred=True)
    last = Message.objects.filter(thread=OuterRef("thread")).order_by(
        "-created_at", "-pk"
    )
    # Never read: every message from the others is new.
    newer = _from_others(user).filter(created_at__gt=OuterRef("read_mark"))
    return (
        rows.annotate(read_mark=Coalesce("last_read_at", Value(NEVER)))
        .annotate(
            last_body=Subquery(last.values("body")[:1]),
            is_unread=Exists(newer),
        )
        .select_related("thread")
        .order_by("-thread__last_message_at", "-pk")
    )


def thread_rows(user: Any, members: list[ThreadMember]) -> list[ThreadRow]:
    """Rows for a page of ``folder_members``, with the other people's names
    (one more query for the page)."""
    others: dict[int, list[str]] = {}
    links = ThreadMember.objects.filter(
        thread_id__in=[member.thread_id for member in members]
    ).exclude(user=user)
    for link in links.select_related("user"):
        name = link.user.get_full_name() or link.user.email
        others.setdefault(link.thread_id, []).append(name)
    return [
        ThreadRow(
            thread=member.thread,
            member=member,
            last_body=member.last_body or "",
            unread=bool(member.is_unread),
            people=", ".join(sorted(others.get(member.thread_id, []))),
        )
        for member in members
    ]


def unread_count(user: Any) -> int:
    """Threads in the Inbox with a message the user has not read."""
    return folder_members(user, "inbox").filter(is_unread=True).count()


# One thread


def member_of(user: Any, thread: Thread) -> ThreadMember | None:
    return ThreadMember.objects.for_user(user).filter(thread=thread).first()


def mark_read(member: ThreadMember, *, now: datetime | None = None) -> None:
    member.last_read_at = now or timezone.now()
    member.save(update_fields=["last_read_at"])


def set_starred(member: ThreadMember, starred: bool) -> None:
    member.starred = starred
    member.save(update_fields=["starred"])


def move_to_trash(member: ThreadMember, *, now: datetime | None = None) -> None:
    member.trashed_at = now or timezone.now()
    member.save(update_fields=["trashed_at"])


def restore(member: ThreadMember) -> None:
    member.trashed_at = None
    member.save(update_fields=["trashed_at"])


def delete_forever(member: ThreadMember) -> None:
    """Only from the Trash. The thread stays for the others in it."""
    if member.trashed_at is None:
        raise ValidationError("Move the conversation to Trash first.")
    member.deleted = True
    member.save(update_fields=["deleted"])


def thread_messages(thread: Thread) -> list[Message]:
    return list(thread.messages.select_related("sender"))


# Drafts


@transaction.atomic
def save_draft(
    owner: Any,
    *,
    recipient: Any,
    subject: str,
    body: str,
    draft: Draft | None = None,
    now: datetime | None = None,
) -> Draft:
    """Keep a new message for later; it needs no recipient or text yet."""
    require_tenant_context(owner.institute)
    errors: dict[str, str] = {}
    subject, body = subject.strip(), body.strip()
    if len(body) > MAX_BODY:
        errors["body"] = f"A message can have {MAX_BODY} characters at most."
    if len(subject) > MAX_SUBJECT:
        errors["subject"] = f"A subject can have {MAX_SUBJECT} characters at most."
    if recipient is not None and not can_message(owner, recipient):
        errors["recipient"] = NOT_REACHABLE
    if errors:
        raise ValidationError(errors)
    draft = draft or Draft(institute_id=owner.institute_id, owner=owner)
    draft.recipient = recipient
    draft.subject = subject
    draft.body = body
    draft.updated_at = now or timezone.now()
    draft.save()
    return draft


@transaction.atomic
def send_draft(
    draft: Draft,
    *,
    recipient: Any,
    subject: str,
    body: str,
    now: datetime | None = None,
) -> Thread:
    thread = send_message(draft.owner, recipient, subject, body, now=now)
    draft.delete()
    return thread
