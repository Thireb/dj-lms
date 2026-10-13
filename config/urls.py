"""Root URL configuration."""

from apps.accounts.views import root_redirect
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
    path("", root_redirect, name="root"),
    path("", include("apps.ui.urls")),
]

# Styled error pages (redesign audit RA1); used when DEBUG is False.
handler403 = "apps.core.responses.handle_403"
handler404 = "apps.core.responses.handle_404"
handler500 = "apps.core.responses.handle_500"
