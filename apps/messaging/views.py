"""Messages pages (roadmap 6.3, FEATURES 11): the folders, one thread with
Reply, and the actions (star, trash, restore, delete forever). Every
portal has the same pages under its own URLs; each user sees only their
own threads (``ThreadMember.objects.for_user``)."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.http import Http404, HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse

from apps.academics.models import Batch
from apps.core import menus as menu_keys
from apps.core.query import id_param, search_param
from apps.core.roles import Role
from apps.messaging.forms import BroadcastForm, ComposeForm, ReplyForm
from apps.messaging.models import Broadcast, Thread
from apps.messaging.services import (
    delete_forever,
    folder_members,
    mark_read,
    member_of,
    monitor_rows,
    monitor_threads,
    move_to_trash,
    reachable,
    reply,
    restore,
    save_draft,
    search_people,
    send_broadcast,
    send_draft,
    send_message,
    set_starred,
    thread_messages,
    thread_rows,
    unread_count,
)
from apps.messaging.ui import (
    MONITOR_NOTICE,
    BroadcastTable,
    MessageTable,
    MonitorTable,
    message_rows,
    person,
)
from apps.ui.components import (
    Button,
    ConfirmDialog,
    FilterBar,
    LinkTabs,
    MessageList,
    Pagination,
    PostButton,
    SectionCard,
)
from apps.ui.components.actions import IconButton
from apps.ui.components.block_stack import BlockStack
from apps.ui.components.data import DetailList
from apps.ui.components.forms import CrispyForm, PortalPostForm
from apps.ui.views.pages import DetailPage, ListPage, PortalPageView

PAGE_SIZE = 25
SEARCH_LIMIT = 10  # people shown for one search on New message
MONITOR_ROLES = {
    Role.INSTITUTE_ADMIN: "Admin",
    Role.SUB_ADMIN: "Sub-admin",
    Role.TEACHER: "Teacher",
    Role.STUDENT: "Student",
    Role.GUARDIAN: "Guardian",
}
REACH_NOTE = (  # SPEC 6.5, in short
    "Students and guardians: the institute office and their teachers. "
    "Teachers: the office, other teachers, and their students and guardians."
)
FOLDER_LABELS = {
    "inbox": "Inbox",
    "sent": "Sent",
    "starred": "Starred",
    "drafts": "Drafts",
    "trash": "Trash",
}
PORTAL_ROLES = {
    "admin": [Role.INSTITUTE_ADMIN, Role.SUB_ADMIN],
    "teacher": [Role.TEACHER],
    "student": [Role.STUDENT],
    "guardian": [Role.GUARDIAN],
}


class MessagingMixin:
    feature_key = "messaging"
    active_item = menu_keys.MESSAGES
    portal = ""

    def url(self, name: str, **kwargs: Any) -> str:
        return reverse(f"{self.portal}:message_{name}", kwargs=kwargs or None)

    def thread_url(self, thread: Thread) -> str:
        return self.url("thread", pk=thread.pk)


class InboxPage(MessagingMixin, ListPage):
    """One folder at a time, chosen with tabs (Inbox, Sent, Starred, Drafts,
    Trash)."""

    title = "Messages"

    def folder(self) -> str:
        wanted = self.request.GET.get("folder", "")
        return wanted if wanted in FOLDER_LABELS else "inbox"

    def get_subtitle(self) -> str:
        return MONITOR_NOTICE

    def get_actions(self) -> list[Any]:
        return [Button("New message", url=self.url("compose"), icon="send")]

    def tabs(self, active: str) -> LinkTabs:
        return LinkTabs(
            [
                {"id": key, "label": label, "url": "?" + urlencode({"folder": key})}
                for key, label in FOLDER_LABELS.items()
            ],
            active=active,
            label="Folders",
        )

    def get_components(self) -> dict[str, Any]:
        folder = self.folder()
        user = self.request.user
        if folder == "drafts":
            table, page = self.drafts_table()
        else:
            page = Paginator(folder_members(user, folder), PAGE_SIZE).get_page(
                self.request.GET.get("page")
            )
            rows = thread_rows(user, list(page.object_list))
            table = MessageTable(rows, open_url=self.thread_url)
        return {
            "filters": self.tabs(folder),
            "table": table,
            "pagination": Pagination(page, query=urlencode({"folder": folder})),
        }

    def drafts_table(self) -> tuple[Any, Any]:
        from apps.messaging.models import Draft
        from apps.messaging.ui import DraftTable

        drafts = Draft.objects.for_user(self.request.user).select_related("recipient")
        page = Paginator(drafts, PAGE_SIZE).get_page(self.request.GET.get("page"))
        table = DraftTable(
            list(page.object_list),
            open_url=lambda draft: f"{self.url('compose')}?draft={draft.pk}",
            delete_url=lambda draft: self.url("draft_delete", pk=draft.pk),
        )
        return table, page


class ThreadPage(MessagingMixin, DetailPage):
    """The messages, oldest first, and Reply. Opening it marks it read."""

    title = "Message"

    def load(self) -> None:
        thread = get_object_or_404(
            Thread.objects.for_user(self.request.user), pk=self.kwargs["pk"]
        )
        self.member = member_of(self.request.user, thread)
        if self.member is None or self.member.deleted:
            raise Http404("No such conversation.")
        self.thread = thread
        self.title = thread.subject

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        self.load()
        self.form = ReplyForm(cancel_url=self.url("inbox"))
        mark_read(self.member)
        return super().get(request, *args, **kwargs)

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        self.load()
        self.form = ReplyForm(request.POST, cancel_url=self.url("inbox"))
        if self.form.is_valid():
            try:
                reply(self.thread, request.user, self.form.cleaned_data["body"])
            except ValidationError as error:
                self.form.add_error(
                    "body" if hasattr(error, "error_dict") else None,
                    error.message_dict.get("body", error.messages)
                    if hasattr(error, "error_dict")
                    else error.messages,
                )
            else:
                messages.success(request, "Reply sent.")
                return HttpResponseRedirect(request.path)
        return self.render_to_response(self.get_context_data())

    def get_subtitle(self) -> str:
        return MONITOR_NOTICE

    def get_actions(self) -> list[Any]:
        action = self.url("action", pk=self.thread.pk)
        member = self.member
        star = "unstar" if member.starred else "star"
        buttons: list[Any] = [
            PostButton(
                "Unstar" if member.starred else "Star",
                f"{action}?do={star}",
                variant="secondary",
                icon="circle-check",
            )
        ]
        if member.trashed_at is None:
            buttons.append(
                PostButton(
                    "Move to Trash",
                    f"{action}?do=trash",
                    variant="secondary",
                    icon="x",
                )
            )
        else:
            buttons.append(
                PostButton(
                    "Restore",
                    f"{action}?do=restore",
                    variant="secondary",
                    icon="arrow-left",
                )
            )
            buttons.append(
                ConfirmDialog(
                    "Delete this conversation forever? It stays for the others in it.",
                    "Delete forever",
                    url=f"{action}?do=delete",
                    trigger_label="Delete forever",
                    dismiss_label="Keep it",
                )
            )
        return buttons

    def get_primary_cards(self) -> list[Any]:
        rows = message_rows(thread_messages(self.thread), self.request.user)
        self.form.helper.disable_csrf = True  # PortalPostForm adds the token
        return [
            SectionCard(title="Conversation", icon="mail", body=MessageList(rows)),
            SectionCard(
                title="Reply",
                icon="send",
                body=PortalPostForm(
                    action=self.request.path,
                    body=CrispyForm(form=self.form),
                    framed=False,
                ),
            ),
        ]

    def get_sidebar_cards(self) -> list[Any]:
        from apps.messaging.models import ThreadMember

        people = ThreadMember.objects.filter(thread=self.thread).select_related("user")
        names = ", ".join(sorted(person(row.user) for row in people))
        rows = [("People", names), ("Note", MONITOR_NOTICE)]
        return [SectionCard(title="Details", icon="list", body=DetailList(rows))]


class ThreadActionView(MessagingMixin, PortalPageView):
    """POST ``?do=star|unstar|trash|restore|delete`` on the user's thread."""

    http_method_names = ["post"]

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        thread = get_object_or_404(
            Thread.objects.for_user(request.user), pk=self.kwargs["pk"]
        )
        member = member_of(request.user, thread)
        if member is None or member.deleted:
            raise Http404("No such conversation.")
        action = request.GET.get("do", "")
        if action in ("star", "unstar"):
            set_starred(member, action == "star")
            return HttpResponseRedirect(self.thread_url(thread))
        if action == "trash":
            move_to_trash(member)
            messages.success(request, "Moved to Trash.")
        elif action == "restore":
            restore(member)
            messages.success(request, "Moved back to the Inbox.")
            return HttpResponseRedirect(self.thread_url(thread))
        elif action == "delete":
            try:
                delete_forever(member)
            except ValidationError as error:
                messages.error(request, " ".join(error.messages))
                return HttpResponseRedirect(self.thread_url(thread))
            messages.success(request, "Deleted forever.")
        else:
            raise Http404("No such action.")
        return HttpResponseRedirect(self.url("inbox"))


class UnreadBadgeView(MessagingMixin, PortalPageView):
    """The menu's unread count (HTMX). A signed-out user gets 204, so HTMX
    does not put the sign-in page in the menu."""

    http_method_names = ["get"]

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        if not request.user.is_authenticated:
            return HttpResponse(status=204)
        return super().dispatch(request, *args, **kwargs)

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        from apps.ui.components import MenuBadge

        return HttpResponse(
            MenuBadge(unread_count(request.user)).render(request=request)
        )


class ComposePage(MessagingMixin, DetailPage):
    """New message: choose the person by search (SPEC 4.19, reach SPEC 6.5),
    then Subject and Message; Send, or Save draft. ``?draft=`` opens a
    draft, ``?to=`` picks the person, ``?q=`` searches."""

    title = "New message"

    def load(self) -> None:
        from apps.messaging.models import Draft

        user = self.request.user
        params = self.request.GET
        self.draft = None
        if params.get("draft"):
            self.draft = get_object_or_404(
                Draft.objects.for_user(user), pk=id_param(params.get("draft"))
            )
        wanted = id_param(params.get("to")) or (
            self.draft.recipient_id if self.draft else None
        )
        self.recipient = reachable(user).filter(pk=wanted).first() if wanted else None
        self.query = search_param(params.get("q"))

    def make_form(self, data: Any = None) -> ComposeForm:
        draft = self.draft
        initial = {"to": self.recipient.pk if self.recipient else None}
        if draft is not None:
            initial.update(subject=draft.subject, body=draft.body)
        return ComposeForm(data, initial=initial, cancel_url=self.url("inbox"))

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        self.load()
        self.form = self.make_form()
        return super().get(request, *args, **kwargs)

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        self.load()
        self.form = self.make_form(request.POST)
        if self.form.is_valid():
            data = self.form.cleaned_data
            user = request.user
            recipient = (
                reachable(user).filter(pk=data["to"]).first() if data["to"] else None
            )
            try:
                if "save_draft" in request.POST:
                    save_draft(
                        user,
                        recipient=recipient,
                        subject=data["subject"],
                        body=data["body"],
                        draft=self.draft,
                    )
                    messages.success(request, "Draft saved.")
                    return HttpResponseRedirect(f"{self.url('inbox')}?folder=drafts")
                if self.draft is not None:
                    thread = send_draft(
                        self.draft,
                        recipient=recipient,
                        subject=data["subject"],
                        body=data["body"],
                    )
                else:
                    thread = send_message(
                        user, recipient, data["subject"], data["body"]
                    )
            except ValidationError as error:
                for name, errors in error.message_dict.items():
                    field = name if name in ("subject", "body") else None
                    self.form.add_error(field, errors)
            else:
                messages.success(request, "Message sent.")
                return HttpResponseRedirect(self.thread_url(thread))
        return self.render_to_response(self.get_context_data())

    def get_subtitle(self) -> str:
        return MONITOR_NOTICE

    def link(self, **params: Any) -> str:
        if self.draft is not None:
            params["draft"] = self.draft.pk
        return f"{self.url('compose')}?{urlencode(params)}"

    def recipient_card(self) -> SectionCard:
        if self.recipient is not None:
            role = self.recipient.get_role_display()
            rows = [
                ("To", f"{person(self.recipient)} ({role})"),
                ("", Button("Choose another person", url=self.link(), variant="ghost")),
            ]
            return SectionCard(title="To", icon="user", body=DetailList(rows))
        filters = FilterBar(
            [
                {
                    "name": "q",
                    "label": "Find a person",
                    "value": self.query,
                    "placeholder": "Name or email",
                },
                *(
                    [
                        {
                            "name": "draft",
                            "label": "",
                            "value": self.draft.pk,
                            "hidden": True,
                        }
                    ]
                    if self.draft
                    else []
                ),
            ]
        )
        found = (
            search_people(self.request.user, self.query, limit=SEARCH_LIMIT)
            if self.query
            else []
        )
        rows = [
            (
                f"{person(user)} ({user.get_role_display()})",
                IconButton(
                    "user-plus", f"Choose {person(user)}", url=self.link(to=user.pk)
                ),
            )
            for user in found
        ]
        if self.query and not rows:
            rows = [("", "No one you can message matches this search.")]
        body = BlockStack(blocks=[filters, DetailList(rows)] if rows else [filters])
        return SectionCard(title="To", icon="user", body=body)

    def get_primary_cards(self) -> list[Any]:
        self.form.helper.disable_csrf = True  # PortalPostForm adds the token
        action = self.request.get_full_path()
        form = PortalPostForm(
            action=action, body=CrispyForm(form=self.form), framed=False
        )
        return [
            self.recipient_card(),
            SectionCard(title="Message", icon="mail", body=form),
        ]

    def get_sidebar_cards(self) -> list[Any]:
        rows = [("Who can you message", REACH_NOTE), ("Note", MONITOR_NOTICE)]
        return [SectionCard(title="About messages", icon="info", body=DetailList(rows))]


class DraftDeleteView(MessagingMixin, PortalPageView):
    http_method_names = ["post"]

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        from apps.messaging.models import Draft

        draft = get_object_or_404(
            Draft.objects.for_user(request.user), pk=self.kwargs["pk"]
        )
        draft.delete()
        messages.success(request, "Draft deleted.")
        return HttpResponseRedirect(f"{self.url('inbox')}?folder=drafts")


# Admin extras (FEATURES 11): Broadcast and Message Monitor


class AdminMessagingMixin(MessagingMixin):
    portal = "admin"
    menu_key = menu_keys.MESSAGES
    allowed_roles = PORTAL_ROLES["admin"]


class BroadcastPage(AdminMessagingMixin, DetailPage):
    title = "Broadcast"

    def make_form(self, data: Any = None) -> BroadcastForm:
        batches = Batch.objects.for_user(self.request.user).filter(is_active=True)
        return BroadcastForm(
            data, batches=batches.order_by("name"), cancel_url=self.url("inbox")
        )

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        self.form = self.make_form()
        return super().get(request, *args, **kwargs)

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        self.form = self.make_form(request.POST)
        if self.form.is_valid():
            data = self.form.cleaned_data
            try:
                broadcast = send_broadcast(
                    request.user,
                    data["audience"],
                    data["subject"],
                    data["body"],
                    batch=data["batch"],
                )
            except ValidationError as error:
                if hasattr(error, "error_dict"):
                    for name, errors in error.message_dict.items():
                        self.form.add_error(
                            name if name in self.form.fields else None, errors
                        )
                else:
                    self.form.add_error(None, error)
            else:
                people = "person" if broadcast.recipients == 1 else "people"
                messages.success(
                    request, f"Broadcast sent to {broadcast.recipients} {people}."
                )
                return HttpResponseRedirect(request.path)
        return self.render_to_response(self.get_context_data())

    def get_subtitle(self) -> str:
        return (
            "Each person gets the message in their own inbox. "
            "A reply comes back only to you."
        )

    def get_primary_cards(self) -> list[Any]:
        self.form.helper.disable_csrf = True  # PortalPostForm adds the token
        form = PortalPostForm(
            action=self.request.path, body=CrispyForm(form=self.form), framed=False
        )
        sent = Broadcast.objects.for_user(self.request.user).select_related("batch")[
            :20
        ]
        return [
            SectionCard(title="New broadcast", icon="send", body=form),
            SectionCard(
                title="Sent broadcasts",
                icon="list",
                body=BroadcastTable(rows=list(sent)),
            ),
        ]


class MonitorPage(AdminMessagingMixin, ListPage):
    """Every thread of the institute (FEATURES 11), read only."""

    title = "Message monitor"

    def get_subtitle(self) -> str:
        return "Every conversation in the institute. Opening one does not mark it read."

    def get_components(self) -> dict[str, Any]:
        query = search_param(self.request.GET.get("q"))
        role = self.request.GET.get("role", "")
        role = role if role in MONITOR_ROLES else ""
        threads = monitor_threads(self.request.user, query=query, role=role)
        page = Paginator(threads, PAGE_SIZE).get_page(self.request.GET.get("page"))
        filters = FilterBar(
            [
                {
                    "name": "q",
                    "label": "Search",
                    "value": query,
                    "placeholder": "Subject, text or name",
                },
                {
                    "name": "role",
                    "label": "Role",
                    "value": role,
                    "options": [("", "Any role"), *MONITOR_ROLES.items()],
                },
            ]
        )
        params = urlencode(
            {key: value for key, value in (("q", query), ("role", role)) if value}
        )
        return {
            "filters": filters,
            "table": MonitorTable(
                monitor_rows(list(page.object_list)),
                open_url=lambda thread: self.url("monitor_thread", pk=thread.pk),
            ),
            "pagination": Pagination(page, query=params),
        }


class MonitorThreadPage(AdminMessagingMixin, DetailPage):
    """One thread, read only; the admin's own read state does not change."""

    title = "Conversation"

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        self.thread = get_object_or_404(
            Thread.objects.for_user(request.user), pk=self.kwargs["pk"]
        )
        self.title = self.thread.subject
        return super().get(request, *args, **kwargs)

    def get_subtitle(self) -> str:
        return "Read only, from the Message Monitor."

    def get_actions(self) -> list[Any]:
        return [
            Button("Back to the monitor", url=self.url("monitor"), variant="secondary")
        ]

    def get_primary_cards(self) -> list[Any]:
        rows = message_rows(thread_messages(self.thread), self.request.user)
        return [SectionCard(title="Conversation", icon="mail", body=MessageList(rows))]

    def get_sidebar_cards(self) -> list[Any]:
        from apps.messaging.models import ThreadMember

        people = ThreadMember.objects.filter(thread=self.thread).select_related("user")
        names = ", ".join(
            sorted(
                f"{person(row.user)} ({row.user.get_role_display()})" for row in people
            )
        )
        return [
            SectionCard(
                title="Details", icon="list", body=DetailList([("People", names)])
            )
        ]


def _for_portal(base: type, portal: str) -> type:
    """The page for one portal: its URLs, roles and (admin) menu key."""
    attrs = {
        "portal": portal,
        "allowed_roles": PORTAL_ROLES[portal],
        "__module__": __name__,
    }
    if portal == "admin":
        attrs["menu_key"] = menu_keys.MESSAGES
    return type(f"{portal.title()}{base.__name__}", (base,), attrs)


PAGES: dict[str, dict[str, type]] = {
    portal: {
        "inbox": _for_portal(InboxPage, portal),
        "thread": _for_portal(ThreadPage, portal),
        "action": _for_portal(ThreadActionView, portal),
        "unread": _for_portal(UnreadBadgeView, portal),
        "compose": _for_portal(ComposePage, portal),
        "draft_delete": _for_portal(DraftDeleteView, portal),
    }
    for portal in PORTAL_ROLES
}
