"""App config for doctor."""

from django.apps import AppConfig


class DoctorConfig(AppConfig):
    """Doctor app — medical queue and decision."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.doctor"
    verbose_name = "Doctor (Medical Queue & Decision)"
