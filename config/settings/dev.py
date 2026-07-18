"""Development settings for RegulaVasc."""

import os

import dj_database_url

from .base import *  # noqa: F401,F403

DEBUG = os.environ.get("DJANGO_DEBUG", "true").lower() in ("true", "1", "yes")

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-secret-key-not-for-production")
ALLOWED_HOSTS = ["*"]

DATABASES = {
    "default": dj_database_url.config(
        default="sqlite:///db.sqlite3",
        conn_max_age=0,
        conn_health_checks=False,
    )
}
