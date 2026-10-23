"""
Django settings for the Domestic Logistics ERP.

This is the Django port of the original FastAPI backend — same models,
same API shape (as close as the two frameworks allow), so the existing
React frontend keeps working by just pointing VITE_API_URL at this server.
"""
import os
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Load a .env file if present (pip install python-dotenv) — mirrors the
# convenience pydantic-settings gave the FastAPI version.
try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env", override=True)
except ImportError:
    pass

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-insecure-secret-change-in-production")
DEBUG = os.environ.get("DJANGO_DEBUG", "True") == "True"
ALLOWED_HOSTS = ["*"] if DEBUG else os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # third-party   
    "rest_framework",
    "rest_framework_simplejwt",
    "corsheaders",
    "django_filters",
    # local apps
    "accounts",
    "vendors",
    "fleet",
    "inventory",
    "orders",
    "dispatch",
    "dashboard",
    "invoices",
    "notifications",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "erp.db",
    }
}

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 6}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- DRF + SimpleJWT ---
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_PAGINATION_CLASS": "config.pagination.StandardPagination",
    "PAGE_SIZE": 50,
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=12),
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# --- CORS: Vite dev server (5173) and preview server (4173) ---
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
]


# ==========================================================================
# Accounting / Invoice Management: Celery + e-mail
# All values come from environment variables (see .env.example); nothing
# secret is hard-coded here.
# ==========================================================================
def _env_bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


# --- Celery (async invoice e-mail). Broker/result backend: Redis ---
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
# We never read Celery task results: the outcome of every invoice e-mail is
# recorded in the InvoiceSendLog table. Ignoring results also means enqueuing
# a task does NOT open a connection to the result backend — without this,
# `.delay()` blocks for ~20 s when Redis is down and would stall the billing
# request.
CELERY_TASK_IGNORE_RESULT = True
# If Redis is down, fail fast (well under a second) instead of hanging the
# billing request; the failure is then recorded on the InvoiceSendLog.
CELERY_TASK_PUBLISH_RETRY_POLICY = {"max_retries": 1, "interval_start": 0, "interval_step": 0.2, "interval_max": 0.5}
CELERY_BROKER_CONNECTION_TIMEOUT = 2
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_BROKER_TRANSPORT_OPTIONS = {"socket_connect_timeout": 2, "socket_timeout": 2}
# Dev convenience: CELERY_TASK_ALWAYS_EAGER=True runs tasks inline (no Redis or
# worker needed). Leave False in production.
CELERY_TASK_ALWAYS_EAGER = _env_bool("CELERY_TASK_ALWAYS_EAGER", False)
CELERY_TASK_EAGER_PROPAGATES = False

# --- E-mail ---
# Default: print e-mails to the runserver/worker console, so a fresh checkout
# needs no SMTP account. For real delivery (e.g. SendGrid) set
# EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend and the EMAIL_*
# variables — see backend/README.md.
EMAIL_BACKEND = os.environ.get("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = os.environ.get("EMAIL_HOST", "smtp.sendgrid.net")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_USE_SSL = _env_bool("EMAIL_USE_SSL", False)
EMAIL_USE_TLS = False if EMAIL_USE_SSL else _env_bool("EMAIL_USE_TLS", True)
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "apikey")
# SendGrid: the SMTP password IS the API key; for Gmail/other SMTP, use the password / app password.
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD") or os.environ.get("SENDGRID_API_KEY", "")
EMAIL_TIMEOUT = int(os.environ.get("EMAIL_TIMEOUT", "15"))
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL") or (
    EMAIL_HOST_USER if "@" in (os.environ.get("EMAIL_HOST_USER") or "") else "noreply@erpsystem.com"
)

# --- Order Notifications ---
# Email address for dispatcher notifications (delivery_failed events).
# If empty, dispatcher email notifications are skipped.
DISPATCHER_NOTIFICATION_EMAIL = os.environ.get("DISPATCHER_NOTIFICATION_EMAIL", "")

# SMS backend: "log" (default, no real SMS) or "twilio"
SMS_BACKEND = os.environ.get("SMS_BACKEND", "log")
SMS_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID") or os.environ.get("SMS_ACCOUNT_SID", "")
SMS_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN") or os.environ.get("SMS_AUTH_TOKEN", "")
SMS_FROM_NUMBER = os.environ.get("TWILIO_FROM_NUMBER") or os.environ.get("SMS_FROM_NUMBER", "")
TWILIO_ACCOUNT_SID = SMS_ACCOUNT_SID
TWILIO_AUTH_TOKEN = SMS_AUTH_TOKEN
TWILIO_FROM_NUMBER = SMS_FROM_NUMBER
