from django.urls import path

from apps.assessments import views as assessments
from apps.attendance import views as attendance
from apps.lectures import views as lectures
from apps.ui.views import portal_home

app_name = "student"

urlpatterns = [
    path("", portal_home.StudentPortalHomePage.as_view(), name="home"),
    path(
        "lectures/<int:pk>/join/",
        lectures.StudentLectureJoinView.as_view(),
        name="lecture_join",
    ),
    path("up-next/", lectures.StudentUpNextCardView.as_view(), name="up_next"),
    path("lectures/", lectures.StudentLectureListPage.as_view(), name="lecture_list"),
    path("attendance/", attendance.StudentAttendancePage.as_view(), name="attendance"),
    path(
        "assignments/",
        assessments.StudentAssignmentListPage.as_view(),
        name="assignment_list",
    ),
    path(
        "assignments/<int:pk>/",
        assessments.StudentAssignmentPage.as_view(),
        name="assignment_detail",
    ),
    path("quizzes/", assessments.StudentQuizListPage.as_view(), name="quiz_list"),
    path(
        "quizzes/<int:pk>/",
        assessments.StudentQuizPage.as_view(),
        name="quiz_detail",
    ),
    path(
        "quizzes/<int:pk>/start/",
        assessments.StudentQuizStartView.as_view(),
        name="quiz_start",
    ),
    path(
        "quizzes/<int:pk>/attempt/",
        assessments.StudentAttemptPage.as_view(),
        name="quiz_attempt",
    ),
]
