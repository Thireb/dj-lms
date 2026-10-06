"""Register test models with Django admin."""

from apps.core.admin import TenantAdmin
from django.contrib import admin

from tests.testapp.models import TenantProbe


@admin.register(TenantProbe)
class TenantProbeAdmin(TenantAdmin):
    list_display = ("label", "institute")
