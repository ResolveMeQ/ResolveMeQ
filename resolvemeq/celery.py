import os
from celery import Celery
import ssl
from django.conf import settings

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'resolvemeq.settings')

app = Celery('resolvemeq')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()

# Get broker URL from environment (supports both local and production)
broker_url = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
result_backend = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')

app.conf.broker_url = broker_url
app.conf.result_backend = result_backend

# Configure SSL settings for Azure Redis (only if using rediss://)
if broker_url.startswith('rediss://'):
    app.conf.broker_use_ssl = {
        'ssl_cert_reqs': None,
        'ssl_ca_certs': None,
        'ssl_certfile': None,
        'ssl_keyfile': None,
    }
    app.conf.broker_connection_retry_on_startup = True

# Configure task settings
app.conf.task_serializer = 'json'
app.conf.result_serializer = 'json'
app.conf.accept_content = ['json']
app.conf.task_track_started = True
app.conf.task_time_limit = 30 * 60  # 30 minutes
app.conf.task_soft_time_limit = 25 * 60  # 25 minutes

# Configure retry settings
app.conf.task_default_retry_delay = 60  # 1 minute
app.conf.task_max_retries = 3

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}') 