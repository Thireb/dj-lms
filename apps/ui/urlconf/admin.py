"""Institute admin portal URLs."""

from django.urls import path

from apps.academics import views as academics
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
    path("classes/", academics.ClassListPage.as_view(), name="class_list"),
    path("classes/add/", academics.ClassCreatePage.as_view(), name="class_create"),
    path(
        "classes/<int:pk>/edit/",
        academics.ClassEditPage.as_view(),
        name="class_edit",
    ),
    path(
        "classes/<int:pk>/status/",
        academics.ClassStatusView.as_view(),
        name="class_status",
    ),
    path("batches/", academics.BatchListPage.as_view(), name="batch_list"),
    path("batches/add/", academics.BatchCreatePage.as_view(), name="batch_create"),
    path(
        "batches/<int:pk>/edit/",
        academics.BatchEditPage.as_view(),
        name="batch_edit",
    ),
    path(
        "batches/<int:pk>/status/",
        academics.BatchStatusView.as_view(),
        name="batch_status",
    ),
    path("subjects/", academics.SubjectListPage.as_view(), name="subject_list"),
    path("subjects/add/", academics.SubjectCreatePage.as_view(), name="subject_create"),
    path(
        "subjects/<int:pk>/edit/",
        academics.SubjectEditPage.as_view(),
        name="subject_edit",
    ),
    path(
        "subjects/<int:pk>/status/",
        academics.SubjectStatusView.as_view(),
        name="subject_status",
    ),
]
