from django.urls import path

from apps.assessments import views as assessments
from apps.attendance import views as attendance
from apps.lectures import views as lectures
from apps.messaging import views as messaging
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
        "quizzes/<int:pk>/event/",
        assessments.StudentQuizEventView.as_view(),
        name="quiz_event",
    ),
    path(
        "quizzes/<int:pk>/attempt/",
        assessments.StudentAttemptPage.as_view(),
        name="quiz_attempt",
    ),
    # Messages (roadmap 6.3)
    path(
        "messages/", messaging.PAGES["student"]["inbox"].as_view(), name="message_inbox"
    ),
    path(
        "messages/new/",
        messaging.PAGES["student"]["compose"].as_view(),
        name="message_compose",
    ),
    path(
        "messages/unread/",
        messaging.PAGES["student"]["unread"].as_view(),
        name="message_unread",
    ),
    path(
        "messages/<int:pk>/",
        messaging.PAGES["student"]["thread"].as_view(),
        name="message_thread",
    ),
    path(
        "messages/<int:pk>/action/",
        messaging.PAGES["student"]["action"].as_view(),
        name="message_action",
    ),
    path(
        "messages/drafts/<int:pk>/delete/",
        messaging.PAGES["student"]["draft_delete"].as_view(),
        name="message_draft_delete",
    ),
]
