"""Register test models with Django admin."""

from apps.core.admin import TenantAdmin
from config.developer_admin_site import developer_admin_site

from tests.testapp.models import TenantProbe


class TenantProbeAdmin(TenantAdmin):
    list_display = ("label", "institute")


developer_admin_site.register(TenantProbe, TenantProbeAdmin)
