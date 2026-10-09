from django.urls import path

from apps.superadmin import views

app_name = "super"

urlpatterns = [
    path("institutes/", views.InstituteListPage.as_view(), name="institute_list"),
    path(
        "institutes/create/",
        views.CreateInstitutePage.as_view(),
        name="institute_create",
    ),
    path(
        "institutes/<int:pk>/edit/",
        views.EditInstitutePage.as_view(),
        name="institute_edit",
    ),
    path(
        "institutes/<int:pk>/status/",
        views.InstituteStatusView.as_view(),
        name="institute_status",
    ),
    path(
        "institutes/<int:pk>/admin-link/",
        views.InstituteAdminLinkPage.as_view(),
        name="institute_admin_link",
    ),
]
