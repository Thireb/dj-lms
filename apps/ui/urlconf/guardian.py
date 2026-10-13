from django.urls import path

from apps.lectures import views as lectures
from apps.ui.views import portal_home

app_name = "guardian"

urlpatterns = [
    path("", portal_home.GuardianPortalHomePage.as_view(), name="home"),
    path(
        "lectures/",
        lectures.GuardianLectureListPage.as_view(),
        name="lecture_schedule",
    ),
]
