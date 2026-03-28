import os
from datetime import timedelta
from pathlib import Path

from celery.schedules import crontab

import dj_database_url
from dotenv import load_dotenv
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.celery import CeleryIntegration

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(os.path.join(BASE_DIR, ".env"))

# Sentry Configuration for Error Monitoring
SENTRY_DSN = os.getenv('SENTRY_DSN', '')
if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[
            DjangoIntegration(),
            CeleryIntegration(),
        ],
        traces_sample_rate=0.1,  # 10% of transactions for performance monitoring
        profiles_sample_rate=0.1,
        environment=os.getenv('ENVIRONMENT', 'production'),
        release=os.getenv('APP_VERSION', '2.0.0'),
        # Filter out sensitive data
        before_send=lambda event, hint: None if 'password' in str(event).lower() else event,
    )

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv(
    "SECRET_KEY",
    "django-insecure-xoeau&915nx&jsisbu$@p4h3^iva-4s4bxov6nj5l@y2l48d%r",
)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv("DEBUG", "False").lower() in ("true", "1", "yes")

raw_hosts = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1")
if raw_hosts == "*":
    ALLOWED_HOSTS = ["*"]
else:
    ALLOWED_HOSTS = [h.strip() for h in raw_hosts.split(",")]
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://app.resolvemeq.net").rstrip("/")
# Application definition

INSTALLED_APPS = [
    "jazzmin",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    'corsheaders',
    'rest_framework',
    "drf_yasg",
    "core",
    "tickets",
    "solutions",
    "knowledge_base",
    "automation",
    "integrations",
    'base',
    'monitoring',
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "resolvemeq.urls"

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
            ],
        },
    },
]

WSGI_APPLICATION = "resolvemeq.wsgi.application"

# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases

"""
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}
"""

_db = {
    'ENGINE': 'django.db.backends.postgresql',
    'NAME': os.getenv('DB_NAME'),
    'USER': os.getenv('DB_USER'),
    'PASSWORD': os.getenv('DB_PASSWORD'),
    'HOST': os.getenv('DB_HOST'),
    'PORT': os.getenv('DB_PORT', '5432'),
}
_db_options = {}
_db_host = os.getenv('DB_HOST') or ''
# Direct db.*.supabase.co is IPv6-only; shared pooler *.pooler.supabase.com supports IPv4 (session mode).
if _db_host.endswith('.supabase.co') or '.pooler.supabase.com' in _db_host:
    _db_options['sslmode'] = 'require'
# Connect via IPv4 when the hostname resolves to IPv6 but the host/Docker network cannot reach it
# ("Network is unreachable"). Set to the A record, e.g. dig +short A db.xxxx.supabase.co
_hostaddr = (os.getenv('DB_HOSTADDR') or '').strip()
if _hostaddr:
    _db_options['hostaddr'] = _hostaddr
if _db_options:
    _db['OPTIONS'] = _db_options

DATABASES = {'default': _db}

CSRF_TRUSTED_ORIGINS = [
    "https://app.resolvemeq.com",
    "https://api.resolvemeq.com",
    "https://agent.resolvemeq.com",
    "https://app.resolvemeq.net",
    "https://api.resolvemeq.net",
    "https://agent.resolvemeq.net",
    "https://resolvemeq.net",
    "https://www.resolvemeq.net",
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:3000",
]

# CORS: merge env with defaults so CORS_ALLOWED_ORIGINS in .env *adds* prod domains without
# stripping localhost (otherwise marketing site on :3000 gets OPTIONS 200 with no ACAO header).
_CORS_DEFAULT_ORIGINS = [
    "https://app.resolvemeq.net",
    "https://resolvemeq.net",
    "https://www.resolvemeq.net",
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
_cors_origins_env = os.getenv("CORS_ALLOWED_ORIGINS", "").strip()
_cors_extra = [o.strip() for o in _cors_origins_env.split(",") if o.strip()] if _cors_origins_env else []
CORS_ALLOWED_ORIGINS = list(dict.fromkeys(_CORS_DEFAULT_ORIGINS + _cors_extra))

CORS_ALLOW_CREDENTIALS = True

CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]

# Django 5 defaults SECURE_CROSS_ORIGIN_OPENER_POLICY to "same-origin", which adds
# Cross-Origin-Opener-Policy on API responses. The SPA should send
# Cross-Origin-Opener-Policy: same-origin-allow-popups (see resolvemeqwebapp public/_headers).
# Disable COOP on JSON API responses unless you set SECURE_CROSS_ORIGIN_OPENER_POLICY explicitly.
_coop = os.getenv("SECURE_CROSS_ORIGIN_OPENER_POLICY", "").strip()
SECURE_CROSS_ORIGIN_OPENER_POLICY = _coop if _coop else None
# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# Internationalization
# https://docs.djangoproject.com/en/4.2/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/
STATIC_URL = "/static/"
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")
# Optionally, if you have extra static directories:
# STATICFILES_DIRS = [os.path.join(BASE_DIR, "static")]

# Serve admin / Jazzmin / DRF static assets in production (Gunicorn has no built-in static handler).
WHITENOISE_MAX_AGE = 60 * 60 * 24 * 30  # 30 days
WHITENOISE_SKIP_COMPRESS_EXTENSIONS = ("jpg", "jpeg", "png", "webp", "zip", "gz", "tgz", "bz2", "tbz", "xz", "br")


# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

SLACK_CLIENT_ID = os.getenv("SLACK_CLIENT_ID")
SLACK_CLIENT_SECRET = os.getenv("SLACK_CLIENT_SECRET")
SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET")
SLACK_REDIRECT_URI = os.getenv("SLACK_REDIRECT_URI")
# Optional: Slack channel ID (e.g. C01234ABCD) to post escalated tickets for support visibility
SLACK_ESCALATION_CHANNEL = os.getenv("SLACK_ESCALATION_CHANNEL", "").strip()

# Google Sign-In (Web client ID; must match VITE_GOOGLE_CLIENT_ID in the frontend)
GOOGLE_OAUTH_CLIENT_ID = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "").strip()

# Plan limits (used for team creation; can be overridden by Subscription later)
PLAN_MAX_TEAMS = int(os.getenv('PLAN_MAX_TEAMS', '20'))

# AI agent quotas (Plan.max_agent_operations_per_month overrides when set; null plan = use default)
# Treat empty env as unset (os.getenv returns '' when the variable is set but blank).
DEFAULT_AGENT_OPERATIONS_PER_MONTH = int((os.getenv('DEFAULT_AGENT_OPERATIONS_PER_MONTH', '500') or '500').strip())
AGENT_OPS_TRIAL_EXPIRED = int((os.getenv('AGENT_OPS_TRIAL_EXPIRED', '0') or '0').strip())

# Billing / payment gateway (see base.billing.gateways.factory)
BILLING_GATEWAY = os.getenv('BILLING_GATEWAY', 'dodo').strip().lower()
DODO_PAYMENTS_API_KEY = os.getenv('DODO_PAYMENTS_API_KEY', '').strip()
# Signing secret from Dodo dashboard (Settings → Webhooks); required for POST /api/billing/webhooks/dodo/
DODO_PAYMENTS_WEBHOOK_KEY = os.getenv('DODO_PAYMENTS_WEBHOOK_KEY', '').strip()
# test_mode (https://test.dodopayments.com) or live_mode (https://live.dodopayments.com)
DODO_PAYMENTS_ENVIRONMENT = os.getenv('DODO_PAYMENTS_ENVIRONMENT', 'test_mode').strip()
BILLING_DEFAULT_CURRENCY = os.getenv('BILLING_DEFAULT_CURRENCY', 'USD').strip()
# Dodo tax_category for API-created products (e.g. saas, digital_products)
BILLING_TAX_CATEGORY = os.getenv('BILLING_TAX_CATEGORY', 'saas').strip()
# Optional default redirect after checkout; else FRONTEND_URL + /billing/complete
BILLING_CHECKOUT_RETURN_URL = os.getenv('BILLING_CHECKOUT_RETURN_URL', '').strip()

# AI Agent Settings
AI_AGENT_URL = 'https://agent.resolvemeq.net/tickets/analyze/'
# Shared secret: Django sends X-API-Key; FastAPI agent rejects requests without it when set.
AI_AGENT_SERVICE_KEY = (os.getenv('AI_AGENT_SERVICE_KEY') or '').strip()
AGENT_API_KEY = os.getenv('AGENT_API_KEY', 'resolvemeq-agent-secret-key-2026')
# LLM confidence thresholds (used by AutonomousAgent and Solution creation in tasks)
AGENT_CONFIDENCE_HIGH = float((os.getenv("AGENT_CONFIDENCE_HIGH", "0.8") or "0.8").strip())
AGENT_CONFIDENCE_MEDIUM = float((os.getenv("AGENT_CONFIDENCE_MEDIUM", "0.6") or "0.6").strip())
AGENT_CONFIDENCE_LOW = float((os.getenv("AGENT_CONFIDENCE_LOW", "0.3") or "0.3").strip())
AGENT_SUCCESS_PROB_AUTO_RESOLVE = float(
    (os.getenv("AGENT_SUCCESS_PROB_AUTO_RESOLVE", "0.8") or "0.8").strip()
)

# Agent Rate Limiting
MAX_AUTONOMOUS_ACTIONS_PER_DAY = int(os.getenv('MAX_AUTONOMOUS_ACTIONS_PER_DAY', '500'))
MAX_AUTONOMOUS_ACTIONS_PER_HOUR = int(os.getenv('MAX_AUTONOMOUS_ACTIONS_PER_HOUR', '100'))

# Redis Settings
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

# Celery Configuration
# Use environment variable (set by Docker) or fallback to local Redis
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', REDIS_URL)
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', CELERY_BROKER_URL)
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_BROKER_HEARTBEAT = 60
CELERY_BROKER_CONNECTION_TIMEOUT = 30

# Celery Beat — periodic emails (run `celery -A resolvemeq beat` in production)
DIGEST_EMAIL_HOUR_UTC = int(os.getenv("DIGEST_EMAIL_HOUR_UTC", "8"))
ENABLE_DIGEST_EMAIL_SCHEDULE = os.getenv(
    "ENABLE_DIGEST_EMAIL_SCHEDULE", "true"
).strip().lower() in ("1", "true", "yes", "")
CELERY_BEAT_SCHEDULE = {}
if ENABLE_DIGEST_EMAIL_SCHEDULE:
    CELERY_BEAT_SCHEDULE["daily-user-digest"] = {
        "task": "base.tasks.send_daily_digest_emails",
        "schedule": crontab(hour=DIGEST_EMAIL_HOUR_UTC, minute=0),
    }

# Optional: token for GET /api/monitoring/health/complete/ (uptime checks without admin JWT)
MONITORING_HEALTH_SECRET = os.getenv("MONITORING_HEALTH_SECRET", "").strip()

# Email Settings
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', 587))
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True').lower() in ['true', '1', 'yes']
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')
# Use a From address on a domain you control; SPF/DKIM/DMARC must authorize this domain or mail lands in spam.
_default_from = os.getenv('DEFAULT_FROM_EMAIL', '').strip()
DEFAULT_FROM_EMAIL = _default_from or EMAIL_HOST_USER or 'webmaster@localhost'
APP_NAME = os.getenv('APP_NAME', 'ResolveMeQ')
# Optional Reply-To for transactional mail (support inbox).
SUPPORT_EMAIL = os.getenv('SUPPORT_EMAIL', '').strip()

# Operator inboxes for ticket escalation alerts (comma-separated). Also set DJANGO_ADMINS for Django-style admin tuples.
_escalation_emails_raw = os.getenv("SUPPORT_ESCALATION_EMAILS", "").strip()
SUPPORT_ESCALATION_EMAILS = (
    [e.strip() for e in _escalation_emails_raw.split(",") if e.strip()]
    if _escalation_emails_raw
    else []
)
# ADMINS: comma-separated "Full Name|ops@company.com" or bare "ops@company.com"
_admins_raw = os.getenv("DJANGO_ADMINS", "").strip()
ADMINS = []
if _admins_raw:
    for part in _admins_raw.split(","):
        part = part.strip()
        if not part:
            continue
        if "|" in part:
            name, em = part.split("|", 1)
            ADMINS.append((name.strip(), em.strip()))
        elif "@" in part:
            ADMINS.append(("Admin", part))

REST_FRAMEWORK = {
    # Do NOT set DEFAULT_SCHEMA_CLASS to drf_yasg.inspectors.SwaggerAutoSchema — it is not a
    # subclass of rest_framework.schemas.inspectors.ViewInspector and breaks @api_view.
    # drf-yasg uses SWAGGER_SETTINGS['DEFAULT_AUTO_SCHEMA_CLASS'] for OpenAPI/Swagger generation.
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'base.authentication.AgentAPIKeyAuthentication',
    ),
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
        'rest_framework.throttling.ScopedRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',
        'user': '1000/hour',
        'agent_actions': '50/minute',  # Max 50 autonomous actions per minute
        'rollback': '10/hour',  # Limit rollback requests
    }
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(days=30),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=75),
}

AUTH_USER_MODEL = 'base.User'

# django-jazzmin (must stay immediately before django.contrib.admin in INSTALLED_APPS)
JAZZMIN_SETTINGS = {
    'site_title': 'ResolveMeQ Admin',
    'site_header': 'ResolveMeQ',
    'site_brand': 'ResolveMeQ',
    'welcome_sign': 'Sign in to manage ResolveMeQ',
    'copyright': 'ResolveMeQ',
    'search_model': ['base.User', 'auth.Group'],
    'topmenu_links': [
        {'name': 'Dashboard', 'url': 'admin:index', 'permissions': ['auth.view_user']},
        {
            'name': 'API docs',
            'url': 'schema-swagger-ui',
            'new_window': True,
        },
    ],
    'icons': {
        'auth': 'fas fa-users-cog',
        'auth.Group': 'fas fa-users',
        'base': 'fas fa-layer-group',
        'base.user': 'fas fa-user',
        'base.team': 'fas fa-people-group',
        'base.plan': 'fas fa-box-open',
        'base.agentusagemonthly': 'fas fa-robot',
        'base.subscription': 'fas fa-receipt',
        'base.invoice': 'fas fa-file-invoice-dollar',
        'base.plangatewayproduct': 'fas fa-plug',
        'base.billingwebhookdelivery': 'fas fa-paper-plane',
        'tickets': 'fas fa-ticket-alt',
        'tickets.ticket': 'fas fa-ticket-alt',
        'monitoring': 'fas fa-chart-line',
    },
    'default_icon_parents': 'fas fa-chevron-circle-right',
    'default_icon_children': 'fas fa-circle',
    'related_modal_active': True,
    'changeform_format': 'horizontal_tabs',
    'show_ui_builder': False,
}

JAZZMIN_UI_TWEAKS = {
    'navbar_small_text': False,
    'footer_small_text': False,
    'body_small_text': False,
    'brand_small_text': False,
    'brand_colour': 'navbar-primary',
    'accent': 'accent-primary',
    'navbar': 'navbar-dark',
    'navbar_fixed': False,
    'layout_boxed': False,
    'footer_fixed': False,
    'sidebar_fixed': True,
    'sidebar': 'sidebar-dark-primary',
    'sidebar_nav_child_indent': True,
    'theme': 'default',
    'button_classes': {
        'primary': 'btn-primary',
        'secondary': 'btn-secondary',
        'info': 'btn-info',
        'warning': 'btn-warning',
        'danger': 'btn-danger',
        'success': 'btn-success',
    },
}

# Swagger Settings (drf-yasg / Swagger UI)
SWAGGER_SETTINGS = {
    # Used by drf-yasg OpenAPISchemaGenerator (not REST_FRAMEWORK.DEFAULT_SCHEMA_CLASS)
    'DEFAULT_AUTO_SCHEMA_CLASS': 'drf_yasg.inspectors.SwaggerAutoSchema',
    'USE_SESSION_AUTH': False,
    'SECURITY_DEFINITIONS': {
        'Bearer': {
            'type': 'apiKey',
            'name': 'Authorization',
            'in': 'header',
            'description': 'JWT access token. Click Authorize and enter: Bearer <paste_access_token_here>',
        },
    },
    'DEFAULT_API_URL': 'https://api.resolvemeq.net' if not DEBUG else 'http://localhost:8000',
    'SUPPORTED_SUBMIT_METHODS': ['get', 'post', 'put', 'delete', 'patch'],
    # Avoid external validator fetch (often blocked / slow in dev)
    'VALIDATOR_URL': None,
    # Expand tag groups so operations (and their Parameters) are easier to find
    'DOC_EXPANSION': 'list',
    # Pass-through to swagger-ui (persist JWT after refresh)
    'SWAGGER_UI_SETTINGS': {
        'persistAuthorization': True,
    },
}
