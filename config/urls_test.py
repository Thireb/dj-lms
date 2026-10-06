"""Test URL configuration (includes HTMX echo endpoint)."""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("accounts/", include("apps.accounts.urls")),
    path("", include("apps.ui.urls")),
    path("", include("tests.testapp.urls")),
]
