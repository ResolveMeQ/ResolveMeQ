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
SECRET_KEY = "django-insecure-xoeau&915nx&jsisbu$@p4h3^iva-4s4bxov6nj5l@y2l48d%r"

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

raw_hosts = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1")
if raw_hosts == "*":
    ALLOWED_HOSTS = ["*"]
else:
    ALLOWED_HOSTS = [h.strip() for h in raw_hosts.split(",")]
FRONTEND_URL = "https://app.resolvemeq.net"
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

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME'),
        'USER': os.getenv('DB_USER'),
        'PASSWORD': os.getenv('DB_PASSWORD'),
        'HOST': os.getenv('DB_HOST'),
        'PORT': os.getenv('DB_PORT', '5432'),
        # 'OPTIONS': {
        #     'sslmode': 'require',
        # },
    }
}

CSRF_TRUSTED_ORIGINS = [
    "https://app.resolvemeq.com",
    "https://api.resolvemeq.com",
    "https://agent.resolvemeq.com",
    "https://app.resolvemeq.net",
    "https://api.resolvemeq.net",
    "https://agent.resolvemeq.net",
    "https://resolvemeq.net",
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:3000",
]

# CORS Settings for React Frontend
CORS_ALLOWED_ORIGINS = [
    "https://app.resolvemeq.net",
    "https://resolvemeq.net",
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:3000",
]

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
AGENT_API_KEY = os.getenv('AGENT_API_KEY', 'resolvemeq-agent-secret-key-2026')

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

REST_FRAMEWORK = {
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

# Swagger Settings
SWAGGER_SETTINGS = {
    'USE_SESSION_AUTH': False,
    'SECURITY_DEFINITIONS': {
        'Basic': {
            'type': 'basic'
        },
        'Bearer': {
            'type': 'apiKey',
            'name': 'Authorization',
            'in': 'header'
        }
    },
    'DEFAULT_API_URL': 'https://api.resolvemeq.net' if not DEBUG else 'http://localhost:8000',
    'SUPPORTED_SUBMIT_METHODS': ['get', 'post', 'put', 'delete', 'patch'],
}
