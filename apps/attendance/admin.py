from config.developer_admin_site import developer_admin_site

from apps.attendance.models import Attendance
from apps.core.admin import TenantAdmin


class AttendanceAdmin(TenantAdmin):
    """Read only. Marks are saved by attendance.services (roster checks)."""

    list_display = ("lecture", "student", "status", "source", "institute")
    list_filter = ("status", "source")

    def has_add_permission(self, request):  # noqa: ANN001
        return False

    def has_change_permission(self, request, obj=None):  # noqa: ANN001
        return False


developer_admin_site.register(Attendance, AttendanceAdmin)
