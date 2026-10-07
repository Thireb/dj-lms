from django.contrib import admin

from apps.core.admin import TenantAdmin
from apps.people.models import GuardianProfile, StudentProfile, TeacherProfile


class ProfileAdmin(TenantAdmin):
    """Read and edit only. Profiles get their codes from people.services."""

    raw_id_fields = ("user",)

    def has_add_permission(self, request):  # noqa: ANN001
        return False


@admin.register(StudentProfile)
class StudentProfileAdmin(ProfileAdmin):
    list_display = ("student_code", "user", "institute", "status")
    list_filter = ("status",)
    readonly_fields = ("student_code", "institute", "user")


@admin.register(TeacherProfile)
class TeacherProfileAdmin(ProfileAdmin):
    list_display = ("teacher_code", "user", "institute", "status")
    list_filter = ("status",)
    readonly_fields = ("teacher_code", "institute", "user")


@admin.register(GuardianProfile)
class GuardianProfileAdmin(ProfileAdmin):
    list_display = ("user", "institute")
    readonly_fields = ("institute", "user")
