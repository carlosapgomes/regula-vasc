"""Base Django settings for RegulaVasc."""

from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent

load_dotenv(BASE_DIR / ".env")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Local apps
    "apps.accounts",
    "apps.cases",
    "apps.llm",
    "apps.pipeline",
    "apps.intake",
    "apps.doctor",
    "apps.dashboard",
]

AUTH_USER_MODEL = "accounts.User"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.accounts.middleware.ActiveRoleMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.accounts.context_processors.role_context",
                "apps.accounts.context_processors.app_display_name",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/login/"

APP_DISPLAY_NAME = "RegulaVasc"

# ── Intake Configuration ──────────────────────────────────────────

INTAKE_MAX_ATTACHMENTS_PER_CASE = 10
INTAKE_MAX_FILES_PER_BATCH = 20
INTAKE_MAX_UPLOAD_BYTES_PER_FILE = 15 * 1024 * 1024  # 15 MB
INTAKE_MAX_UPLOAD_BYTES_PER_BATCH = 50 * 1024 * 1024  # 50 MB
INTAKE_MAX_ATTACHMENT_BYTES_PER_FILE = 10 * 1024 * 1024  # 10 MB
INTAKE_MAX_ATTACHMENT_BYTES_PER_CASE = 50 * 1024 * 1024  # 50 MB

# ── Lock Configuration ───────────────────────────────────────────

CASE_LOCK_LEASE_SECONDS = 900  # 15 minutes

# Email (dev usa console backend, definido em dev.py)
PASSWORD_RESET_TIMEOUT = 3600 * 24  # 24h
DEFAULT_FROM_EMAIL = "noreply@regulavasc.hospital.org"

# ── LLM Configuration ────────────────────────────────────────────────

OPENAI_API_KEY = ""
OPENAI_MODEL = "gpt-4o-mini"
OPENAI_BASE_URL = "https://api.openai.com/v1"

# LLM1 (Structured Extraction)
LLM1_PRIMARY_PROVIDER = "openai"
LLM1_PRIMARY_MODEL = "gpt-4o-mini"
LLM1_PRIMARY_API_KEY = ""
LLM1_PRIMARY_BASE_URL = ""

LLM1_SECONDARY_PROVIDER = "openai"
LLM1_SECONDARY_MODEL = "gpt-4o-mini"
LLM1_SECONDARY_API_KEY = ""
LLM1_SECONDARY_BASE_URL = ""

# LLM2 (Suggestion)
LLM2_PRIMARY_PROVIDER = "openai"
LLM2_PRIMARY_MODEL = "gpt-4o-mini"
LLM2_PRIMARY_API_KEY = ""
LLM2_PRIMARY_BASE_URL = ""

LLM2_SECONDARY_PROVIDER = "openai"
LLM2_SECONDARY_MODEL = "gpt-4o-mini"
LLM2_SECONDARY_API_KEY = ""
LLM2_SECONDARY_BASE_URL = ""

# Dual-LLM toggle
LLM_SECONDARY_ENABLED = False

# Anthropic (optional)
ANTHROPIC_API_KEY = ""
ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
ANTHROPIC_BASE_URL = "https://api.anthropic.com"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Bahia"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DATA_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024  # 20 MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024  # 20 MB

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
