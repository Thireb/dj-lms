from django.http import HttpRequest, HttpResponse
from django.views.decorators.http import require_POST


@require_POST
def htmx_echo(request: HttpRequest) -> HttpResponse:
    return HttpResponse("htmx-ok", content_type="text/plain")
