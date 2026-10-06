from django.urls import path

from apps.ui.views import portal_home

app_name = "guardian"

urlpatterns = [
    path("", portal_home.GuardianPortalHomePage.as_view(), name="home"),
]
