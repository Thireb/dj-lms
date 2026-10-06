from django.urls import path

from apps.ui.views import portal_home

app_name = "teacher"

urlpatterns = [
    path("", portal_home.TeacherPortalHomePage.as_view(), name="home"),
]
