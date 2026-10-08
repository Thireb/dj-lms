from config.developer_admin_site import developer_admin_site

from apps.core.admin import TenantAdmin
from apps.people.models import (
    GuardianProfile,
    GuardianStudentLink,
    StudentProfile,
    TeacherProfile,
)


class ProfileAdmin(TenantAdmin):
    """Read and edit only. Profiles get their codes from people.services.

    Status is read-only: it must change together with User.is_active, which
    only the people services do (audit L5).
    """

    def has_add_permission(self, request):  # noqa: ANN001
        return False


class StudentProfileAdmin(ProfileAdmin):
    list_display = ("student_code", "user", "institute", "status")
    list_filter = ("status",)
    readonly_fields = ("student_code", "institute", "user", "status")


class TeacherProfileAdmin(ProfileAdmin):
    list_display = ("teacher_code", "user", "institute", "status")
    list_filter = ("status",)
    readonly_fields = ("teacher_code", "institute", "user", "status")


class GuardianProfileAdmin(ProfileAdmin):
    list_display = ("user", "institute")
    readonly_fields = ("institute", "user")


class GuardianStudentLinkAdmin(ProfileAdmin):
    list_display = ("guardian", "student", "institute", "created_at")
    readonly_fields = ("institute", "guardian", "student")


developer_admin_site.register(StudentProfile, StudentProfileAdmin)
developer_admin_site.register(TeacherProfile, TeacherProfileAdmin)
developer_admin_site.register(GuardianProfile, GuardianProfileAdmin)
developer_admin_site.register(GuardianStudentLink, GuardianStudentLinkAdmin)
