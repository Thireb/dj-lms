"""Test URL configuration (includes HTMX echo endpoint)."""

from django.contrib import admin
from django.http import HttpResponse
from django.urls import include, path


def accounts_logout_stub(request):  # noqa: ANN001
    return HttpResponse("logout ok")


accounts_urlpatterns = [
    path("logout/", accounts_logout_stub, name="logout"),
]

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("accounts/", include((accounts_urlpatterns, "accounts"))),
    path("", include("apps.ui.urls")),
    path("", include("tests.testapp.urls")),
]
