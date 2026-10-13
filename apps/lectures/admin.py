from config.developer_admin_site import developer_admin_site

from apps.core.admin import TenantAdmin
from apps.lectures.models import Lecture


class LectureAdmin(TenantAdmin):
    """Read only. Lectures are saved by lectures.services (overlap checks)."""

    list_display = ("title", "teacher", "batch", "starts_at", "status", "institute")
    list_filter = ("status", "delivery_mode")
    search_fields = ("title",)

    def has_add_permission(self, request):  # noqa: ANN001
        return False

    def has_change_permission(self, request, obj=None):  # noqa: ANN001
        return False


developer_admin_site.register(Lecture, LectureAdmin)
