"""Django developer admin (not the product admin portal)."""

from apps.accounts import throttle
from django.contrib.admin import AdminSite
from django.contrib.admin.forms import AdminAuthenticationForm
from django.core.exceptions import ValidationError


class ThrottledAdminLoginForm(AdminAuthenticationForm):
    """Shares the sign-in failure limit with the product login (audit H1)."""

    def clean(self):
        email = self.data.get("username", "")
        ip = throttle.client_ip(self.request)
        if throttle.is_locked(throttle.LOGIN, email, ip):
            raise ValidationError(throttle.LOCKED_MESSAGE, code="throttled")
        try:
            cleaned = super().clean()
        except ValidationError:
            throttle.record_failure(throttle.LOGIN, email, ip)
            raise
        throttle.reset(throttle.LOGIN, email, ip)
        return cleaned


developer_admin_site = AdminSite(name="developer")
developer_admin_site.login_form = ThrottledAdminLoginForm
