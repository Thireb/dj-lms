"""Institute admin portal URLs."""

from django.urls import path

from apps.institutes.views import CampusProfilePage, InstituteSettingsPage
from apps.ui.views import portal_home

app_name = "admin"

urlpatterns = [
    path("", portal_home.AdminPortalHomePage.as_view(), name="home"),
    path("campus/", CampusProfilePage.as_view(), name="campus"),
    path(
        "settings/institute/",
        InstituteSettingsPage.as_view(),
        name="institute_settings",
    ),
]
