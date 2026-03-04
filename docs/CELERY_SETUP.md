# Celery Worker Setup Guide

## Overview

This project uses Celery for asynchronous task processing, particularly for AI agent ticket analysis. Redis serves as the message broker and result backend.

## Architecture

- **Message Broker**: Redis (localhost:6379/0 for local, VPS Redis for production)
- **Result Backend**: Redis
- **Worker Pool**: Solo for local development, Prefork for production
- **Tasks**: AI ticket processing, email notifications, autonomous actions

## Local Development Setup

### Option 1: Run Celery Worker (Recommended)

The prefork pool doesn't work reliably on all local machines. Use the **solo pool** instead:

```bash
# Activate virtual environment
source venv/bin/activate

# Start Celery worker with solo pool
celery -A resolvemeq worker -l info --pool=solo
```

Keep this running in a separate terminal while developing. The worker will:
- ✅ Process tasks asynchronously
- ✅ Match production behavior
- ✅ Allow testing of real Celery workflows

### Option 2: Force Synchronous Processing

If you don't want to run a Celery worker locally, set this in `.env`:

```bash
FORCE_SYNC_AGENT_PROCESSING=true
```

This will:
- ⚠️ Process tasks synchronously (blocking)
- ⚠️ Skip Celery queue entirely
- ⚠️ Not match production behavior
- ✅ Work without any Celery worker running

## Production (VPS) Setup

### 1. Install Celery and Dependencies

```bash
pip install celery redis
```

### 2. Configure Environment Variables

In `.env` on VPS:

```bash
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
REDIS_PASSWORD=your_redis_password

# Use async Celery in production
FORCE_SYNC_AGENT_PROCESSING=false
```

### 3. Start Celery Worker with Systemd

Create `/etc/systemd/system/resolvemeq-celery.service`:

```ini
[Unit]
Description=ResolveMeQ Celery Worker
After=network.target redis.service

[Service]
Type=forking
User=www-data
Group=www-data
WorkingDirectory=/var/www/resolvemeq
Environment="PATH=/var/www/resolvemeq/venv/bin"
ExecStart=/var/www/resolvemeq/venv/bin/celery -A resolvemeq worker \
          --loglevel=info \
          --pool=prefork \
          --concurrency=4 \
          --logfile=/var/log/celery/worker.log \
          --pidfile=/var/run/celery/worker.pid

ExecStop=/var/www/resolvemeq/venv/bin/celery -A resolvemeq control shutdown
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 4. Create Log Directories

```bash
sudo mkdir -p /var/log/celery /var/run/celery
sudo chown www-data:www-data /var/log/celery /var/run/celery
```

### 5. Enable and Start Service

```bash
sudo systemctl daemon-reload
sudo systemctl enable resolvemeq-celery
sudo systemctl start resolvemeq-celery
sudo systemctl status resolvemeq-celery
```

## Verifying Celery is Working

### Check Worker Status

```bash
# Via Celery inspect
celery -A resolvemeq inspect active

# Via process list
ps aux | grep celery

# Via systemd (production)
sudo systemctl status resolvemeq-celery
```

### Check Redis Connection

```bash
redis-cli ping  # Should return "PONG"

# Check queued tasks
redis-cli -n 0 LLEN celery

# Monitor Redis in real-time
redis-cli MONITOR
```

### Test Task Processing

```python
# In Django shell
from tickets.tasks import process_ticket_with_agent

# Queue a test task
result = process_ticket_with_agent.delay(ticket_id=123)

# Check task status
print(result.status)  # Should be 'SUCCESS' when done
print(result.ready())  # True when complete
print(result.result)  # Task return value
```

## Common Issues

### Exit Code 148

**Problem**: Celery worker exits with code 148 when using prefork pool locally.

**Solution**: Use `--pool=solo` for local development:
```bash
celery -A resolvemeq worker -l info --pool=solo
```

### No Workers Connected

**Problem**: Tasks stay in PENDING state forever.

**Diagnosis**:
```python
from celery import current_app
i = current_app.control.inspect()
print(i.active())  # Should show worker(s)
print(i.registered())  # Should show tasks
```

**Solution**: 
1. Verify Celery worker is running
2. Check Redis connection
3. Ensure correct broker URL in settings

### Tasks Not Processing

**Problem**: Worker is running but doesn't pick up tasks.

**Solution**:
1. Check worker logs for errors
2. Verify task is registered: `celery -A resolvemeq inspect registered`
3. Restart worker: `sudo systemctl restart resolvemeq-celery`
4. Clear stale tasks: `celery -A resolvemeq purge`

### OSError: [Errno 24] Too many open files

**Problem**: Worker crashes with file descriptor limit error.

**Solution**: Increase file descriptor limit:
```bash
# In systemd service file, add:
LimitNOFILE=65536

# Or system-wide in /etc/systemd/system.conf:
DefaultLimitNOFILE=65536
```

## Monitoring

### Real-time Monitoring with Flower

```bash
# Install Flower
pip install flower

# Start Flower dashboard
celery -A resolvemeq flower --port=5555

# Access at http://localhost:5555
```

### Check Task Results in Redis

```bash
# List all keys
redis-cli KEYS *

# Get task result
redis-cli GET celery-task-meta-<task_id>
```

### View Worker Logs

```bash
# Local development
# (Output is in the terminal where worker is running)

# Production with systemd
sudo journalctl -u resolvemeq-celery -f

# Production with log file
tail -f /var/log/celery/worker.log
```

## Performance Tuning

### Concurrency

```bash
# Auto-detect CPU cores
celery -A resolvemeq worker --autoscale=10,3

# Fixed concurrency
celery -A resolvemeq worker --concurrency=4
```

### Task Time Limits

In `tickets/tasks.py`:

```python
@shared_task(bind=True, time_limit=300, soft_time_limit=270)
def process_ticket_with_agent(self, ticket_id):
    # Task will be killed after 300 seconds
    # SoftTimeLimitExceeded raised after 270 seconds
    pass
```

### Memory Management

```python
# In resolvemeq/celery.py
app.conf.worker_max_tasks_per_child = 1000  # Restart worker after 1000 tasks
app.conf.worker_prefetch_multiplier = 4     # Prefetch 4 tasks per worker
```

## Environment Variables Reference

| Variable | Local Dev | VPS Production | Description |
|----------|-----------|----------------|-------------|
| `REDIS_URL` | `redis://localhost:6379/0` | `redis://localhost:6379/0` | Broker connection |
| `CELERY_BROKER_URL` | Same as REDIS_URL | Same as REDIS_URL | Message broker |
| `CELERY_RESULT_BACKEND` | Same as REDIS_URL | Same as REDIS_URL | Result storage |
| `FORCE_SYNC_AGENT_PROCESSING` | `false` (with worker) or `true` (without) | `false` | Bypass Celery |
| `REDIS_PASSWORD` | Optional | **Required** | Redis auth |

## Quick Reference Commands

```bash
# Start worker (local development)
celery -A resolvemeq worker -l info --pool=solo

# Start worker (production)
celery -A resolvemeq worker -l info --pool=prefork --concurrency=4

# Check worker status
celery -A resolvemeq inspect active

# Check registered tasks
celery -A resolvemeq inspect registered

# Purge all tasks
celery -A resolvemeq purge

# Stop all workers
celery -A resolvemeq control shutdown

# Restart specific worker
celery -A resolvemeq control pool_restart

# Monitor events
celery -A resolvemeq events
```

## Next Steps

1. **Local Development**: Start worker with `celery -A resolvemeq worker -l info --pool=solo`
2. **Test Processing**: Create a ticket and click "Get AI Help" button
3. **Production**: Set up systemd service and monitor logs
4. **Optimization**: Adjust concurrency based on VPS resources

For more information, see:
- [Celery Documentation](https://docs.celeryproject.org/)
- [Django Celery Integration](https://docs.celeryproject.org/en/stable/django/)
- [AGENT_API.md](./AGENT_API.md) for endpoint usage
