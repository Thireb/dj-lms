from django.urls import path

from apps.lectures import views as lectures
from apps.ui.views import portal_home

app_name = "teacher"

urlpatterns = [
    path("", portal_home.TeacherPortalHomePage.as_view(), name="home"),
    path("lectures/", lectures.TeacherLectureListPage.as_view(), name="lecture_list"),
    path(
        "lectures/create/",
        lectures.TeacherLectureCreatePage.as_view(),
        name="lecture_create",
    ),
    path(
        "lectures/<int:pk>/edit/",
        lectures.TeacherLectureEditPage.as_view(),
        name="lecture_edit",
    ),
]
