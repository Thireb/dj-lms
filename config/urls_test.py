"""Test URL configuration (includes HTMX echo endpoint)."""

from django.urls import include, path

from config.developer_admin_site import developer_admin_site

urlpatterns = [
    path("django-admin/", developer_admin_site.urls),
    path("accounts/", include("apps.accounts.urls")),
    path("admin/", include("apps.ui.urlconf.admin")),
    path("teacher/", include("apps.ui.urlconf.teacher")),
    path("student/", include("apps.ui.urlconf.student")),
    path("guardian/", include("apps.ui.urlconf.guardian")),
    path("super/", include("apps.superadmin.urls")),
    path("", include("apps.ui.urls")),
    path("", include("tests.testapp.urls")),
]
