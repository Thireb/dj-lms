"""Institute admin portal URLs (campus and settings)."""

from apps.institutes import views
from django.urls import path

app_name = "admin"

urlpatterns = [
    path("campus/", views.CampusProfilePage.as_view(), name="campus"),
    path(
        "settings/institute/",
        views.InstituteSettingsPage.as_view(),
        name="institute_settings",
    ),
]
