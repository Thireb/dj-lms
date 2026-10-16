"""Institute admin portal URLs."""

from django.urls import path

from apps.academics import views as academics
from apps.assessments import views as assessments
from apps.attendance import views as attendance
from apps.finance import views as finance
from apps.institutes.views import CampusProfilePage, InstituteSettingsPage
from apps.lectures import views as lectures
from apps.messaging import views as messaging
from apps.people import views as people

app_name = "admin"

urlpatterns = [
    path("", people.AdminDashboardPage.as_view(), name="home"),
    path("dashboard/", people.AdminDashboardPage.as_view(), name="dashboard_main"),
    path(
        "dashboard/lectures/",
        lectures.LecturesDashboardPage.as_view(),
        name="dashboard_lectures",
    ),
    path("campus/", CampusProfilePage.as_view(), name="campus"),
    path(
        "settings/institute/",
        InstituteSettingsPage.as_view(),
        name="institute_settings",
    ),
    path("classes/", academics.ClassListPage.as_view(), name="class_list"),
    path("classes/add/", academics.ClassCreatePage.as_view(), name="class_create"),
    path(
        "classes/<int:pk>/edit/",
        academics.ClassEditPage.as_view(),
        name="class_edit",
    ),
    path(
        "classes/<int:pk>/status/",
        academics.ClassStatusView.as_view(),
        name="class_status",
    ),
    path("batches/", academics.BatchListPage.as_view(), name="batch_list"),
    path("batches/add/", academics.BatchCreatePage.as_view(), name="batch_create"),
    path(
        "batches/<int:pk>/edit/",
        academics.BatchEditPage.as_view(),
        name="batch_edit",
    ),
    path(
        "batches/<int:pk>/status/",
        academics.BatchStatusView.as_view(),
        name="batch_status",
    ),
    path("subjects/", academics.SubjectListPage.as_view(), name="subject_list"),
    path("subjects/add/", academics.SubjectCreatePage.as_view(), name="subject_create"),
    path(
        "subjects/<int:pk>/edit/",
        academics.SubjectEditPage.as_view(),
        name="subject_edit",
    ),
    path(
        "subjects/<int:pk>/status/",
        academics.SubjectStatusView.as_view(),
        name="subject_status",
    ),
    path("teachers/", people.TeacherListPage.as_view(), name="teacher_list"),
    path("teachers/add/", people.TeacherCreatePage.as_view(), name="teacher_create"),
    path(
        "teachers/<int:pk>/edit/",
        people.TeacherEditPage.as_view(),
        name="teacher_edit",
    ),
    path(
        "teachers/<int:pk>/status/",
        people.TeacherStatusView.as_view(),
        name="teacher_status",
    ),
    path("students/", people.StudentListPage.as_view(), name="student_list"),
    path("students/enrol/", people.StudentEnrolPage.as_view(), name="student_create"),
    path(
        "students/<int:pk>/edit/",
        people.StudentEditPage.as_view(),
        name="student_edit",
    ),
    path(
        "students/<int:pk>/status/",
        people.StudentStatusView.as_view(),
        name="student_status",
    ),
    path(
        "students/upload/",
        people.StudentBulkUploadPage.as_view(),
        name="student_bulk_upload",
    ),
    path(
        "students/upload/import/",
        people.StudentBulkImportView.as_view(),
        name="student_bulk_import",
    ),
    path(
        "students/upload/template/",
        people.StudentBulkTemplateView.as_view(),
        name="student_bulk_template",
    ),
    path("quizzes/", assessments.AdminQuizListPage.as_view(), name="quiz_list"),
    path(
        "quizzes/<int:pk>/",
        assessments.AdminQuizPage.as_view(),
        name="quiz_detail",
    ),
    path("lectures/", lectures.LectureListPage.as_view(), name="lecture_list"),
    path("lectures/add/", lectures.LectureCreatePage.as_view(), name="lecture_create"),
    path(
        "lectures/<int:pk>/",
        lectures.LectureDetailPage.as_view(),
        name="lecture_detail",
    ),
    path(
        "lectures/<int:pk>/edit/",
        lectures.LectureEditPage.as_view(),
        name="lecture_edit",
    ),
    path(
        "lectures/<int:pk>/cancel/",
        lectures.LectureCancelView.as_view(),
        name="lecture_cancel",
    ),
    path(
        "teachers/lecture-history/",
        lectures.AdminLectureHistoryPage.as_view(),
        name="teacher_lecture_history",
    ),
    path(
        "lectures/schedules/",
        lectures.ScheduleListPage.as_view(),
        name="lecture_schedule_list",
    ),
    path(
        "lectures/schedules/add/",
        lectures.ScheduleCreatePage.as_view(),
        name="lecture_schedule_create",
    ),
    path(
        "lectures/schedules/<int:pk>/edit/",
        lectures.ScheduleEditPage.as_view(),
        name="lecture_schedule_edit",
    ),
    path(
        "lectures/schedules/<int:pk>/extend/",
        lectures.ScheduleExtendPage.as_view(),
        name="lecture_schedule_extend",
    ),
    path(
        "lectures/schedules/<int:pk>/stop/",
        lectures.ScheduleStopView.as_view(),
        name="lecture_schedule_stop",
    ),
    path(
        "students/attendance/",
        attendance.AdminStudentAttendancePage.as_view(),
        name="student_attendance_history",
    ),
    path("portal-access/", people.PortalAccessPage.as_view(), name="portal_access"),
    path(
        "portal-access/<int:pk>/",
        people.PortalAccessActionView.as_view(),
        name="portal_access_action",
    ),
    # Messages (roadmap 6.3)
    path(
        "messages/", messaging.PAGES["admin"]["inbox"].as_view(), name="message_inbox"
    ),
    path(
        "messages/new/",
        messaging.PAGES["admin"]["compose"].as_view(),
        name="message_compose",
    ),
    path(
        "messages/unread/",
        messaging.PAGES["admin"]["unread"].as_view(),
        name="message_unread",
    ),
    path(
        "messages/<int:pk>/",
        messaging.PAGES["admin"]["thread"].as_view(),
        name="message_thread",
    ),
    path(
        "messages/<int:pk>/action/",
        messaging.PAGES["admin"]["action"].as_view(),
        name="message_action",
    ),
    path(
        "messages/drafts/<int:pk>/delete/",
        messaging.PAGES["admin"]["draft_delete"].as_view(),
        name="message_draft_delete",
    ),
    path(
        "messages/broadcast/",
        messaging.BroadcastPage.as_view(),
        name="message_broadcast",
    ),
    path("messages/monitor/", messaging.MonitorPage.as_view(), name="message_monitor"),
    path(
        "messages/monitor/<int:pk>/",
        messaging.MonitorThreadPage.as_view(),
        name="message_monitor_thread",
    ),
    # Fees (Phase 7)
    path("fee-plans/", finance.FeePlanListPage.as_view(), name="fee_plan_list"),
    path("fee-plans/add/", finance.FeePlanCreatePage.as_view(), name="fee_plan_create"),
    path(
        "fee-plans/<int:pk>/edit/",
        finance.FeePlanEditPage.as_view(),
        name="fee_plan_edit",
    ),
    path(
        "fee-plans/<int:pk>/status/",
        finance.FeePlanStatusView.as_view(),
        name="fee_plan_status",
    ),
    path("challans/", finance.ChallanListPage.as_view(), name="challan_list"),
    path(
        "challans/generate/",
        finance.ChallanGeneratePage.as_view(),
        name="challan_generate",
    ),
    path(
        "challans/<int:pk>/", finance.ChallanDetailPage.as_view(), name="challan_detail"
    ),
    path(
        "challans/<int:pk>/cancel/",
        finance.ChallanCancelView.as_view(),
        name="challan_cancel",
    ),
    path("challans/print/", finance.ChallanPrintView.as_view(), name="challan_print"),
    path(
        "challans/<int:pk>/pdf/", finance.ChallanPdfView.as_view(), name="challan_pdf"
    ),
    path(
        "challans/<int:pk>/pay/", finance.ChallanPayPage.as_view(), name="challan_pay"
    ),
    path("payments/", finance.PaymentProcessPage.as_view(), name="payment_process"),
    path(
        "payments/<int:pk>/receipt/",
        finance.PaymentReceiptView.as_view(),
        name="payment_receipt",
    ),
    path(
        "students/<int:pk>/fees/",
        finance.StudentFeeHistoryPage.as_view(),
        name="student_fee_history",
    ),
    path("receipts/", finance.ReceiptInboxPage.as_view(), name="receipt_inbox"),
    path(
        "receipts/<int:pk>/", finance.ReceiptDetailPage.as_view(), name="receipt_detail"
    ),
    path(
        "receipts/<int:pk>/approve/",
        finance.ReceiptApproveView.as_view(),
        name="receipt_approve",
    ),
    path(
        "receipts/<int:pk>/reject/",
        finance.ReceiptRejectView.as_view(),
        name="receipt_reject",
    ),
    path(
        "receipts/<int:pk>/file/",
        finance.AdminReceiptFileView.as_view(),
        name="receipt_file",
    ),
    path("fees/daily/", finance.DailyReportPage.as_view(), name="fee_report_daily"),
    path(
        "fees/monthly/", finance.MonthlyReportPage.as_view(), name="fee_report_monthly"
    ),
    path("fees/yearly/", finance.YearlyReportPage.as_view(), name="fee_report_yearly"),
    path(
        "fees/defaulters/", finance.FeeDefaultersPage.as_view(), name="fee_defaulters"
    ),
    path(
        "dashboard/challan/",
        finance.ChallanDashboardPage.as_view(),
        name="dashboard_challan",
    ),
]
