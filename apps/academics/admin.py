from config.developer_admin_site import developer_admin_site

from apps.academics.models import (
    Batch,
    ClassLabel,
    StudentBatchSubject,
    Subject,
    TeacherBatchSubject,
)
from apps.core.admin import TenantAdmin


class NameListAdmin(TenantAdmin):
    list_display = ("name", "institute", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name",)

    def get_readonly_fields(self, request, obj=None):  # noqa: ANN001
        return ("institute",) if obj is not None else ()


class LinkAdmin(TenantAdmin):
    """Read only. Links are set by academics.services."""

    def has_add_permission(self, request):  # noqa: ANN001
        return False

    def has_change_permission(self, request, obj=None):  # noqa: ANN001
        return False


class StudentBatchSubjectAdmin(LinkAdmin):
    list_display = ("student", "batch", "subject", "institute")


class TeacherBatchSubjectAdmin(LinkAdmin):
    list_display = ("teacher", "batch", "subject", "institute")


developer_admin_site.register(ClassLabel, NameListAdmin)
developer_admin_site.register(Batch, NameListAdmin)
developer_admin_site.register(Subject, NameListAdmin)
developer_admin_site.register(StudentBatchSubject, StudentBatchSubjectAdmin)
developer_admin_site.register(TeacherBatchSubject, TeacherBatchSubjectAdmin)
