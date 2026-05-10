"""
Use for local/agent tests without Postgres: `manage.py test --settings=resolvemeq.sqlite_test_settings`
"""
from resolvemeq.settings import *  # noqa: F403, F401

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "test_sqlite.sqlite3",
    }
}
