from django.urls import path

from apps.attendance import views as attendance
from apps.lectures import views as lectures
from apps.ui.views import portal_home

app_name = "teacher"

urlpatterns = [
    path("", portal_home.TeacherPortalHomePage.as_view(), name="home"),
    path("up-next/", lectures.UpNextCardView.as_view(), name="up_next"),
    path("lectures/", lectures.TeacherLectureListPage.as_view(), name="lecture_list"),
    path("schedule/", lectures.TeacherCalendarPage.as_view(), name="schedule"),
    path(
        "lectures/create/",
        lectures.TeacherLectureCreatePage.as_view(),
        name="lecture_create",
    ),
    path(
        "lectures/<int:pk>/",
        lectures.TeacherLectureDetailPage.as_view(),
        name="lecture_detail",
    ),
    path(
        "lectures/<int:pk>/edit/",
        lectures.TeacherLectureEditPage.as_view(),
        name="lecture_edit",
    ),
    path(
        "lectures/<int:pk>/start/",
        lectures.TeacherLectureStartView.as_view(),
        name="lecture_start",
    ),
    path(
        "lectures/<int:pk>/end/",
        lectures.TeacherLectureEndView.as_view(),
        name="lecture_end",
    ),
    path(
        "lectures/<int:pk>/attendance/",
        attendance.TakeAttendancePage.as_view(),
        name="lecture_attendance",
    ),
    path(
        "lectures/history/",
        lectures.TeacherLectureHistoryPage.as_view(),
        name="lecture_history",
    ),
    path(
        "lectures/schedules/",
        lectures.TeacherScheduleListPage.as_view(),
        name="lecture_schedule_list",
    ),
    path(
        "lectures/schedules/add/",
        lectures.TeacherScheduleCreatePage.as_view(),
        name="lecture_schedule_create",
    ),
    path(
        "lectures/schedules/<int:pk>/edit/",
        lectures.TeacherScheduleEditPage.as_view(),
        name="lecture_schedule_edit",
    ),
    path(
        "lectures/schedules/<int:pk>/extend/",
        lectures.TeacherScheduleExtendPage.as_view(),
        name="lecture_schedule_extend",
    ),
    path(
        "lectures/schedules/<int:pk>/stop/",
        lectures.TeacherScheduleStopView.as_view(),
        name="lecture_schedule_stop",
    ),
]
