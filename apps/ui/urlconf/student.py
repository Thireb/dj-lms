from django.urls import path

from apps.ui.views import portal_home

app_name = "student"

urlpatterns = [
    path("", portal_home.StudentPortalHomePage.as_view(), name="home"),
]
