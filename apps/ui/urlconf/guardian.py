from django.urls import path

from apps.assessments import views as assessments
from apps.attendance import views as attendance
from apps.lectures import views as lectures
from apps.people import views as people
from apps.ui.views import portal_home

app_name = "guardian"

urlpatterns = [
    path("", portal_home.GuardianPortalHomePage.as_view(), name="home"),
    path("child/", people.GuardianChooseChildView.as_view(), name="choose_child"),
    path(
        "lectures/",
        lectures.GuardianLectureListPage.as_view(),
        name="lecture_schedule",
    ),
    path("attendance/", attendance.GuardianAttendancePage.as_view(), name="attendance"),
    path(
        "assignments/",
        assessments.GuardianAssignmentListPage.as_view(),
        name="assignment_list",
    ),
    path("quizzes/", assessments.GuardianQuizListPage.as_view(), name="quiz_list"),
]
