from django.urls import path

from apps.accounts import views
from apps.ui.views import portal_home

app_name = "accounts"

urlpatterns = [
    path("login/", views.LoginView.as_view(), name="login"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    path("home/admin/", portal_home.AdminPortalHomePage.as_view(), name="admin_home"),
    path(
        "home/teacher/",
        portal_home.TeacherPortalHomePage.as_view(),
        name="teacher_home",
    ),
    path(
        "home/student/",
        portal_home.StudentPortalHomePage.as_view(),
        name="student_home",
    ),
    path(
        "home/guardian/",
        portal_home.GuardianPortalHomePage.as_view(),
        name="guardian_home",
    ),
    path(
        "home/super-admin/",
        portal_home.SuperAdminPortalHomePage.as_view(),
        name="super_admin_home",
    ),
    path(
        "forgot-password/",
        views.ForgotPasswordView.as_view(),
        name="forgot_password",
    ),
    path(
        "set-password/<str:token>/",
        views.SetPasswordView.as_view(),
        name="set_password",
    ),
    path("profile/", views.ProfileView.as_view(), name="profile"),
    path(
        "change-password/",
        views.ChangePasswordView.as_view(),
        name="change_password",
    ),
]
