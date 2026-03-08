# Verify Celery is Using Redis on VPS

## Quick Verification Commands

Run these commands on your VPS to verify Celery → Redis connection:

---

## 1. Check If Redis is Running

```bash
# Check Redis service status
sudo systemctl status redis-server

# OR if using Docker
docker ps | grep redis

# Test Redis connectivity
redis-cli ping
# Should return: PONG

# If password protected
redis-cli -a YOUR_PASSWORD ping
```

---

## 2. Check Celery Worker Configuration

```bash
# SSH to VPS
ssh user@your-vps-ip

# If using Docker
cd /opt/ResolveMeQ  # or your deployment path

# Check running Celery workers
docker ps | grep celery

# Check Celery worker logs
docker logs resolvemeq-celery-1 --tail 50

# Look for lines like:
# - ** ---------- .> transport:   redis://redis:6379/0
# - ** ---------- .> results:     redis://redis:6379/0
```

---

## 3. Monitor Redis in Real-Time

Open **TWO SSH sessions** to VPS:

### Terminal 1: Monitor Redis commands
```bash
# Watch Redis commands in real-time
redis-cli MONITOR

# OR with password
redis-cli -a YOUR_PASSWORD MONITOR

# You should see commands like:
# "GET" "celery-task-meta-abc123"
# "SET" "celery-task-meta-xyz789"
# "LPUSH" "celery"
```

### Terminal 2: Trigger a test task
```bash
# Activate venv (if not using Docker)
source /opt/ResolveMeQ/venv/bin/activate

# OR enter Django container
docker exec -it resolvemeq-web-1 bash

# Run Django shell
python manage.py shell

# Send test task
from core.tasks import test_task
result = test_task.delay()
print(f"Task ID: {result.id}")
```

**Expected:** Terminal 1 should show Redis activity immediately!

---

## 4. Check Redis Keys Created by Celery

```bash
# Connect to Redis
redis-cli

# OR with password
redis-cli -a YOUR_PASSWORD

# List all keys (careful on production!)
redis> KEYS *

# You should see keys like:
# - celery-task-meta-<uuid>
# - _kombu.binding.*
# - unacked_mutex

# Count Celery-related keys
redis> KEYS celery* | wc -l
redis> KEYS _kombu* | wc -l

# Check specific task result
redis> GET celery-task-meta-YOUR-TASK-ID

# Exit Redis
redis> exit
```

---

## 5. Check Celery Worker Stats

```bash
# If using Docker
docker exec -it resolvemeq-celery-1 celery -A resolvemeq inspect stats

# OR if not using Docker
cd /opt/ResolveMeQ
source venv/bin/activate
celery -A resolvemeq inspect stats

# Expected output includes:
# - broker: {'transport': 'redis', ...}
# - pool: {'max-concurrency': 8, ...}
```

---

## 6. Send Real Ticket Processing Task

```bash
# Enter Django shell
docker exec -it resolvemeq-web-1 python manage.py shell

# OR
cd /opt/ResolveMeQ && source venv/bin/activate && python manage.py shell
```

```python
from tickets.models import Ticket
from tickets.tasks import process_ticket_with_agent
from base.models import User

# Create test ticket
user = User.objects.first()
ticket = Ticket.objects.create(
    user=user,
    issue_type="Test VPS Celery - printer issue",
    description="Testing Celery on VPS",
    category="printer",
    status="new"
)

print(f"Created ticket #{ticket.ticket_id}")

# Trigger Celery task
task = process_ticket_with_agent.delay(ticket.ticket_id)
print(f"Task ID: {task.id}")
print(f"Task State: {task.state}")

# Wait a few seconds
import time
time.sleep(5)

# Check result
from celery.result import AsyncResult
result = AsyncResult(task.id)
print(f"Final State: {result.state}")
print(f"Ready: {result.ready()}")

# Verify ticket was processed
ticket.refresh_from_db()
print(f"Agent Processed: {ticket.agent_processed}")

# Cleanup
ticket.delete()
print("Test complete!")
```

---

## 7. Check Environment Variables

```bash
# Verify REDIS_URL is set correctly
docker exec resolvemeq-web-1 env | grep REDIS
docker exec resolvemeq-celery-1 env | grep REDIS

# Should show something like:
# REDIS_URL=redis://redis:6379/0
# CELERY_BROKER_URL=redis://redis:6379/0
# CELERY_RESULT_BACKEND=redis://redis:6379/0
```

---

## 8. Check Docker Network Connectivity

```bash
# Verify services are on same network
docker network inspect resolvemeq-shared

# Should show all services:
# - resolvemeq-web-1
# - resolvemeq-celery-1
# - resolvemeq-redis-1 (or similar)

# Test connectivity from Django to Redis
docker exec resolvemeq-web-1 ping redis -c 3

# Test from Celery worker to Redis
docker exec resolvemeq-celery-1 ping redis -c 3
```

---

## 9. Full Integration Test

Run this complete test on VPS:

```bash
#!/bin/bash
echo "=== CELERY + REDIS VERIFICATION SCRIPT ==="

echo -e "\n1. Redis Status:"
docker ps | grep redis || echo "❌ Redis not running!"

echo -e "\n2. Celery Worker Status:"
docker ps | grep celery || echo "❌ Celery not running!"

echo -e "\n3. Redis Connectivity:"
docker exec resolvemeq-web-1 redis-cli -h redis ping

echo -e "\n4. Celery Worker Info:"
docker exec resolvemeq-celery-1 celery -A resolvemeq inspect active

echo -e "\n5. Redis Keys Count:"
docker exec resolvemeq-web-1 redis-cli -h redis DBSIZE

echo -e "\n6. Environment Check:"
docker exec resolvemeq-web-1 env | grep -E "REDIS_URL|CELERY"

echo -e "\n=== VERIFICATION COMPLETE ==="
```

Save this as `verify_celery_redis.sh` and run:
```bash
chmod +x verify_celery_redis.sh
./verify_celery_redis.sh
```

---

## 10. Check Celery Flower (Optional)

If you have Flower monitoring installed:

```bash
# Access Flower web UI
# Navigate to: http://your-vps-ip:5555

# Check:
# - Workers tab: Shows active workers
# - Tasks tab: Shows task history
# - Broker tab: Shows Redis connection status
```

---

## Common Issues & Solutions

### Issue 1: Celery Shows "redis://localhost" Instead of "redis://redis"

```bash
# Check environment variables
docker exec resolvemeq-celery-1 env | grep CELERY_BROKER_URL

# Should be: redis://redis:6379/0
# NOT: redis://localhost:6379/0

# Fix: Update docker-compose.yml
# environment:
#   - CELERY_BROKER_URL=redis://redis:6379/0
```

### Issue 2: Connection Refused

```bash
# Check if Redis is on same Docker network
docker network inspect resolvemeq-shared | grep -A5 redis

# Check Redis logs
docker logs resolvemeq-redis-1
```

### Issue 3: Tasks Not Processing

```bash
# Check Celery worker logs
docker logs resolvemeq-celery-1 --tail 100

# Look for errors:
# - "Connection refused"
# - "Authentication failed"
# - "No such file or directory"

# Restart Celery worker
docker restart resolvemeq-celery-1
```

---

## Expected Healthy Output

When everything is working correctly:

### Redis CLI Monitor:
```
1709518234.123456 [0 172.18.0.3:45678] "GET" "celery-task-meta-abc123"
1709518234.234567 [0 172.18.0.3:45678] "SET" "celery-task-meta-abc123" "..."
1709518234.345678 [0 172.18.0.3:45678] "LPUSH" "celery" "..."
```

### Celery Worker Logs:
```
[2026-03-04 10:30:00,000: INFO/MainProcess] Connected to redis://redis:6379/0
[2026-03-04 10:30:05,123: INFO/MainProcess] Task tickets.tasks.process_ticket_with_agent received
[2026-03-04 10:30:05,456: INFO/ForkPoolWorker-1] Task tickets.tasks.process_ticket_with_agent succeeded
```

### Django Shell:
```python
>>> task.state
'SUCCESS'
>>> ticket.agent_processed
True
```

---

## Quick Health Check One-Liner

```bash
docker exec resolvemeq-celery-1 celery -A resolvemeq inspect ping && \
docker exec resolvemeq-web-1 redis-cli -h redis ping && \
echo "✅ Celery + Redis are connected!"
```

---

## Summary

✅ **All working if you see:**
- Redis service running
- Celery worker logs show `redis://redis:6379/0`
- `redis-cli MONITOR` shows activity when tasks run
- Tasks complete successfully
- `inspect ping` returns active workers

❌ **Not working if:**
- Connection refused errors
- `redis://localhost` instead of `redis://redis`
- No activity in Redis monitor
- Tasks stuck in PENDING state
