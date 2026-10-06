from django.apps import AppConfig


class InstitutesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.institutes"
    label = "institutes"

    def ready(self) -> None:
        from apps.institutes import signals  # noqa: F401
