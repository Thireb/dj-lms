from config.developer_admin_site import developer_admin_site

from apps.assessments.models import Assignment, Submission
from apps.core.admin import TenantAdmin


class AssignmentAdmin(TenantAdmin):
    """Read only. Assignments are saved by assessments.services."""

    list_display = ("title", "teacher", "batch", "subject", "due_at", "institute")
    search_fields = ("title",)

    def has_add_permission(self, request):  # noqa: ANN001
        return False

    def has_change_permission(self, request, obj=None):  # noqa: ANN001
        return False


class SubmissionAdmin(TenantAdmin):
    """Read only. Answers and grades are saved by assessments.services."""

    list_display = ("assignment", "student", "submitted_at", "marks", "institute")

    def has_add_permission(self, request):  # noqa: ANN001
        return False

    def has_change_permission(self, request, obj=None):  # noqa: ANN001
        return False


developer_admin_site.register(Assignment, AssignmentAdmin)
developer_admin_site.register(Submission, SubmissionAdmin)
