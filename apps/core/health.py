"""Uptime check (backlog S13): open to everyone, shows no data."""

from __future__ import annotations

import logging

from django.db import DatabaseError, connection
from django.http import HttpRequest, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe

logger = logging.getLogger(__name__)


@never_cache
@require_safe
def health(request: HttpRequest) -> JsonResponse:
    """200 when the database answers, else 503. The error goes to the log,
    not to the caller."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except DatabaseError:
        logger.exception("Health check: the database did not answer.")
        return JsonResponse({"status": "error"}, status=503)
    return JsonResponse({"status": "ok"})
