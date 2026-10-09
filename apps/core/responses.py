"""Full-page refusals for signed-in users who cannot use the portal (audit L1)."""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.urls import reverse


def blocked_account_response(request: HttpRequest, message: str) -> HttpResponse:
    """403 page with the reason and a Sign out button."""
    # Imported here: apps.ui imports apps.core, not the other way at load time.
    from apps.ui.components.actions import SignOutForm
    from apps.ui.components.block_stack import BlockStack
    from apps.ui.components.layout import PublicFormShell, SectionCard

    card = SectionCard(
        title="Access refused",
        body=BlockStack(
            blocks=[message, SignOutForm(logout_url=reverse("accounts:logout"))]
        ),
    )
    shell = PublicFormShell(page_title="Access refused", content=card)
    return HttpResponse(shell.render(request=request), status=403)
