# Test Configuration
# Add this to your settings.py or create a separate test_settings.py

import os
import sys
from resolvemeq.settings import *

# Test database configuration
if 'test' in sys.argv:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': ':memory:',
        }
    }

# Disable celery during tests
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Use a mock agent URL for testing
AGENT_API_URL = 'http://mock-agent.test/api/analyze'

# Disable agent processing during most tests
TEST_DISABLE_AGENT = True

# Disable migrations during testing for speed
class DisableMigrations:
    def __contains__(self, item):
        return True

    def __getitem__(self, item):
        return None

if 'test' in sys.argv:
    MIGRATION_MODULES = DisableMigrations()

# Test-specific settings
if 'test' in sys.argv:
    DEBUG = True

    # Disable logging during tests
    LOGGING = {
        'version': 1,
        'disable_existing_loggers': False,
        'handlers': {
            'null': {
                'class': 'logging.NullHandler',
            },
        },
        'root': {
            'handlers': ['null'],
        },
    }
    
    # Use in-memory cache
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        }
    }
    
    # Disable Celery during tests
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_EAGER_PROPAGATES = True
    
    # Mock external services
    AI_AGENT_URL = 'http://mock-agent.test/api/analyze'
    
    # Speed up password hashing
    PASSWORD_HASHERS = [
        'django.contrib.auth.hashers.MD5PasswordHasher',
    ]
