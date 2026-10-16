from django.urls import path

from apps.assessments import views as assessments
from apps.attendance import views as attendance
from apps.finance import views as finance
from apps.lectures import views as lectures
from apps.messaging import views as messaging
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
    # Messages (roadmap 6.3)
    path(
        "messages/",
        messaging.PAGES["guardian"]["inbox"].as_view(),
        name="message_inbox",
    ),
    path(
        "messages/new/",
        messaging.PAGES["guardian"]["compose"].as_view(),
        name="message_compose",
    ),
    path(
        "messages/unread/",
        messaging.PAGES["guardian"]["unread"].as_view(),
        name="message_unread",
    ),
    path(
        "messages/<int:pk>/",
        messaging.PAGES["guardian"]["thread"].as_view(),
        name="message_thread",
    ),
    path(
        "messages/<int:pk>/action/",
        messaging.PAGES["guardian"]["action"].as_view(),
        name="message_action",
    ),
    path(
        "messages/drafts/<int:pk>/delete/",
        messaging.PAGES["guardian"]["draft_delete"].as_view(),
        name="message_draft_delete",
    ),
    # Fees (Phase 7)
    path("fees/", finance.GuardianFeesPage.as_view(), name="fee_list"),
    path(
        "fees/challans/<int:pk>/pdf/",
        finance.GuardianChallanPdfView.as_view(),
        name="challan_pdf",
    ),
    path("fees/pay/", finance.GuardianFeePayPage.as_view(), name="fee_pay"),
    path(
        "fees/receipts/<int:pk>/file/",
        finance.GuardianReceiptFileView.as_view(),
        name="receipt_file",
    ),
]
