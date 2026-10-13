from django.urls import path

from apps.lectures import views as lectures
from apps.ui.views import portal_home

app_name = "student"

urlpatterns = [
    path("", portal_home.StudentPortalHomePage.as_view(), name="home"),
    path("lectures/", lectures.StudentLectureListPage.as_view(), name="lecture_list"),
]
