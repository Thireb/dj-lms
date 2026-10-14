"""Institute admin portal URLs."""

from django.urls import path

from apps.academics import views as academics
from apps.institutes.views import CampusProfilePage, InstituteSettingsPage
from apps.lectures import views as lectures
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
    path("portal-access/", people.PortalAccessPage.as_view(), name="portal_access"),
    path(
        "portal-access/<int:pk>/",
        people.PortalAccessActionView.as_view(),
        name="portal_access_action",
    ),
]
