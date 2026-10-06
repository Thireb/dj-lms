from django.urls import path

from tests.testapp import views
from tests.ui.support.page_views import (
    DemoAdminDashboard,
    DemoAdminPeopleList,
    DemoTeacherDashboard,
    DemoTenantProbeFormPage,
)

urlpatterns = [
    path("test/htmx-echo/", views.htmx_echo, name="test_htmx_echo"),
    path(
        "test/pages/admin-dashboard/",
        DemoAdminDashboard.as_view(),
        name="test_admin_dashboard",
    ),
    path(
        "test/pages/teacher-dashboard/",
        DemoTeacherDashboard.as_view(),
        name="test_teacher_dashboard",
    ),
    path(
        "test/pages/admin-people/",
        DemoAdminPeopleList.as_view(),
        name="test_admin_people",
    ),
    path(
        "test/pages/tenant-probe-form/",
        DemoTenantProbeFormPage.as_view(),
        name="test_tenant_probe_form",
    ),
]
