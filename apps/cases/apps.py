"""AppConfig for cases."""

from django.apps import AppConfig


class CasesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.cases"
    label = "cases"
    verbose_name = "Casos e Fluxo"

    def ready(self) -> None:
        """Import signal handlers."""
        import apps.cases.signals  # noqa: F401
