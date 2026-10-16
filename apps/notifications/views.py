"""Notification pages (roadmap 6.1): the list, the bell's count and panel,
Open and Mark all as read. Every role but the super admin has them; each
user sees only their own (``Notification.objects.for_user``)."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from django.contrib import messages
from django.core.paginator import Paginator
from django.http import Http404, HttpRequest, HttpResponse, HttpResponseRedirect
from django.urls import reverse

from apps.core.roles import Role
from apps.notifications.models import Notification
from apps.notifications.services import latest, mark_all_read, mark_read, unread_count
from apps.notifications.ui import NotificationTable, panel_rows
from apps.ui.components import NotificationCount, NotificationPanel, Pagination
from apps.ui.components.actions import PostButton
from apps.ui.menus.registry import portal_for_user
from apps.ui.views.pages import ListPage, PortalPageView

PAGE_SIZE = 25
NOTIFICATION_ROLES = [
    Role.INSTITUTE_ADMIN,
    Role.SUB_ADMIN,
    Role.TEACHER,
    Role.STUDENT,
    Role.GUARDIAN,
]


def list_url() -> str:
    return reverse("notifications:list")


def back_path(value: str) -> str:
    """A path in this site from a full URL or a path; else the list. The
    host is dropped, so "https://other.site/x" can only go to "/x"."""
    parts = urlsplit(value or "")
    path = parts.path
    bad = "\\" in path or not value.isprintable()  # browsers read a backslash as "/"
    if not path.startswith("/") or path.startswith("//") or bad:
        return list_url()
    return f"{path}?{parts.query}" if parts.query else path


class NotificationMixin:
    """Self-service like My profile: every portal, no admin menu key."""

    allowed_roles = NOTIFICATION_ROLES
    self_service = True

    def setup(self, request: HttpRequest, *args: Any, **kwargs: Any) -> None:
        super().setup(request, *args, **kwargs)
        self.portal = portal_for_user(request.user)


class BellPartMixin(NotificationMixin):
    """A part of the bell that HTMX loads. A signed-out user gets 204, so
    HTMX does not put the sign-in page inside the bell."""

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        if not request.user.is_authenticated:
            return HttpResponse(status=204)
        return super().dispatch(request, *args, **kwargs)


class NotificationListPage(NotificationMixin, ListPage):
    title = "Notifications"

    def get_subtitle(self) -> str:
        return "Your notifications from the last 90 days."

    def get_actions(self) -> list[Any]:
        if not unread_count(self.request.user):
            return []
        url = reverse("notifications:read_all")
        return [PostButton("Mark all as read", url, variant="secondary", icon="check")]

    def get_components(self) -> dict[str, Any]:
        rows = Notification.objects.for_user(self.request.user)
        page = Paginator(rows, PAGE_SIZE).get_page(self.request.GET.get("page"))
        return {
            "table": NotificationTable(list(page.object_list)),
            "pagination": Pagination(page),
        }


class NotificationCountView(BellPartMixin, PortalPageView):
    http_method_names = ["get"]

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        count = NotificationCount(unread_count(request.user))
        return HttpResponse(count.render(request=request))


class NotificationPanelView(BellPartMixin, PortalPageView):
    http_method_names = ["get"]

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        panel = NotificationPanel(
            panel_rows(latest(request.user)),
            list_url=list_url(),
            read_all_url=reverse("notifications:read_all"),
            # HTMX names the page the bell is on; Mark all as read goes back.
            next_url=back_path(request.headers.get("HX-Current-URL", "")),
        )
        return HttpResponse(panel.render(request=request))


class NotificationOpenView(NotificationMixin, PortalPageView):
    """POST: mark the notification read and open its link."""

    http_method_names = ["post"]

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        row = mark_read(request.user, self.kwargs["pk"])
        if row is None:
            raise Http404("No such notification.")
        return HttpResponseRedirect(row.link or list_url())


class NotificationReadAllView(NotificationMixin, PortalPageView):
    http_method_names = ["post"]

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        mark_all_read(request.user)
        messages.success(request, "All notifications are marked as read.")
        return HttpResponseRedirect(back_path(request.POST.get("next", "")))
