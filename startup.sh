#!/bin/bash

# Set environment variables for Celery
export CELERY_BROKER_URL="rediss://:vB2Ugfa35AuoUt75oQTLK5a7MGLWCmNVOAzCaBPJWXI=@resolvemeq-cache.redis.cache.windows.net:6380/0"
export CELERY_RESULT_BACKEND="rediss://:vB2Ugfa35AuoUt75oQTLK5a7MGLWCmNVOAzCaBPJWXI=@resolvemeq-cache.redis.cache.windows.net:6380/0"
export CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP=True

# Start Celery worker with prefork pool for production VPS
celery -A resolvemeq worker --loglevel=info --pool=prefork --concurrency=4 