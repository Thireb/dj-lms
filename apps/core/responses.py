"""Full-page refusals for signed-in users who cannot use the portal (audit L1)."""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.urls import reverse


def blocked_account_response(request: HttpRequest, message: str) -> HttpResponse:
    """403 page with the reason and a Sign out button."""
    # Imported here: apps.ui imports apps.core, not the other way at load time.
    from apps.ui.components.actions import SignOutForm
    from apps.ui.components.block_stack import BlockStack
    from apps.ui.components.layout import PageHeader, PublicFormShell

    shell = PublicFormShell(
        page_title="Access refused",
        header=PageHeader(title="Access refused"),
        content=BlockStack(
            blocks=[
                message,
                SignOutForm(logout_url=reverse("accounts:logout"), variant="light"),
            ]
        ),
        variant="notice",
        icon="lock",
    )
    return HttpResponse(shell.render(request=request), status=403)


# Error pages in the Lexicon look (redesign audit RA1). Each one is a
# "notice" page: the band, an icon, what happened, and a way home.
ERROR_PAGES = {
    403: (
        "lock",
        "No access to this page",
        "Your account cannot open this page. Ask your institute admin if you need it.",
    ),
    404: (
        "search",
        "Page not found",
        "The link may be old or mistyped. Check the address, or go back to your "
        "home page.",
    ),
    500: (
        "triangle-alert",
        "Something went wrong",
        "The page could not load. Try again in a minute. If it keeps happening, "
        "contact the institute office.",
    ),
}


def error_response(request: HttpRequest, status: int) -> HttpResponse:
    """The styled page for 403, 404 or 500, with a link to the home page."""
    from apps.ui.components.actions import Button
    from apps.ui.components.block_stack import BlockStack
    from apps.ui.components.layout import PageHeader, PublicFormShell

    icon, title, text = ERROR_PAGES[status]
    shell = PublicFormShell(
        page_title=title,
        header=PageHeader(title=title),
        content=BlockStack(
            blocks=[
                text,
                Button("Go to my home page", variant="light", url="/", icon="house"),
            ]
        ),
        variant="notice",
        icon=icon,
    )
    return HttpResponse(shell.render(request=request), status=status)


def forbidden_response(request: HttpRequest) -> HttpResponse:
    return error_response(request, 403)


def handle_403(
    request: HttpRequest, exception: Exception | None = None
) -> HttpResponse:
    return error_response(request, 403)


def handle_404(
    request: HttpRequest, exception: Exception | None = None
) -> HttpResponse:
    return error_response(request, 404)


def handle_500(request: HttpRequest) -> HttpResponse:
    return error_response(request, 500)
