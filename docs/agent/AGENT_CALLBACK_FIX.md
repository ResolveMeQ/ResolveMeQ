# Agent Callback Configuration Fix

## 🔴 Current Issue

**Status:** Agent receives requests from Django but can't update ticket status back

**Error:** `"Failed to analyze ticket: 500: Failed to update ticket status in Django backend"`

**Root Cause:** The AI Agent at `https://agent.resolvemeq.net` is missing environment variables to communicate back to Django.

---

## 📊 Communication Flow

```
┌─────────────┐                           ┌──────────────┐
│   Django    │  1. POST /tickets/analyze │  AI Agent    │
│  Backend    │──────────────────────────>│ (FastAPI)    │
│             │                            │              │
│             │  2. Agent processes ticket │              │
│             │                            │              │
│             │  3. POST /api/tickets/{id}/status/       │
│             │<──────────────────────────│              │
│             │     ❌ FAILING HERE        │              │
└─────────────┘                           └──────────────┘
```

**Step 1 ✅ Working:** Django → Agent  
**Step 3 ❌ Failing:** Agent → Django (missing config)

---

## ✅ Django Configuration (Already Complete)

### 1. Authentication System
- ✅ `AgentAPIKeyAuthentication` in `base/authentication.py`
- ✅ `IsAuthenticatedOrAgent` permission in `base/permissions.py`
- ✅ Registered in `REST_FRAMEWORK['DEFAULT_AUTHENTICATION_CLASSES']`

### 2. API Endpoint
- ✅ `POST /api/tickets/<ticket_id>/status/` accepts agent auth
- ✅ Expects header: `X-Agent-API-Key: resolvemeq-agent-secret-key-2026`

### 3. Environment Variables
```bash
# In Django .env (already set)
AI_AGENT_URL=https://agent.resolvemeq.net/tickets/analyze/
AGENT_API_KEY=resolvemeq-agent-secret-key-2026
```

---

## ⚠️ Agent Configuration (NEEDS SETUP)

The AI Agent needs these environment variables configured:

### Required Environment Variables

```bash
# Django Backend URL (where agent should POST callbacks)
DJANGO_BACKEND_URL=https://resolvemeq.net

# Authentication key to send in X-Agent-API-Key header
DJANGO_API_KEY=resolvemeq-agent-secret-key-2026
# OR
AGENT_API_KEY=resolvemeq-agent-secret-key-2026
```

### Agent Code Requirements

The agent's FastAPI code should:

1. **Read environment variable:**
```python
import os
DJANGO_BACKEND_URL = os.getenv('DJANGO_BACKEND_URL', 'http://localhost:8000')
DJANGO_API_KEY = os.getenv('DJANGO_API_KEY') or os.getenv('AGENT_API_KEY')
```

2. **Send POST request with authentication:**
```python
import httpx

async def update_ticket_status(ticket_id: int, status: str):
    url = f"{DJANGO_BACKEND_URL}/api/tickets/{ticket_id}/status/"
    headers = {
        "Content-Type": "application/json",
        "X-Agent-API-Key": DJANGO_API_KEY
    }
    data = {"status": status}
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=data, headers=headers)
        response.raise_for_status()
```

3. **Update ticket during analysis:**
```python
@app.post("/tickets/analyze/")
async def analyze_ticket(ticket: TicketAnalysisRequest):
    try:
        # Process ticket with AI
        solution = await generate_ai_solution(ticket)
        
        # Update Django backend
        await update_ticket_status(
            ticket_id=ticket.ticket_id,
            status="in-progress"
        )
        
        # Store result in Django
        await store_agent_response(
            ticket_id=ticket.ticket_id,
            response=solution
        )
        
        return {"status": "success", "solution": solution}
    except Exception as e:
        logger.error(f"Failed to analyze ticket: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

---

## 🚀 Deployment Steps

### Option 1: Manual Configuration (If you have agent server access)

1. **SSH into agent server:**
```bash
ssh user@agent.resolvemeq.net
```

2. **Update agent's .env file:**
```bash
echo "DJANGO_BACKEND_URL=https://resolvemeq.net" >> /path/to/agent/.env
echo "DJANGO_API_KEY=resolvemeq-agent-secret-key-2026" >> /path/to/agent/.env
```

3. **Restart agent service:**
```bash
sudo systemctl restart agent-service
# OR
docker-compose restart agent
# OR
pm2 restart agent
```

### Option 2: Environment Variables via Docker Compose

If agent uses Docker Compose, update `docker-compose.yml`:

```yaml
services:
  agent:
    image: ghcr.io/yourusername/agent:latest
    environment:
      - DJANGO_BACKEND_URL=https://resolvemeq.net
      - DJANGO_API_KEY=resolvemeq-agent-secret-key-2026
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    ports:
      - "8001:8000"
```

Then redeploy:
```bash
docker-compose down
docker-compose up -d
```

### Option 3: GitHub Actions Workflow

If agent has automated deployment, update workflow secrets:

1. Go to agent repository → Settings → Secrets
2. Add secrets:
   - `DJANGO_BACKEND_URL` = `https://resolvemeq.net`
   - `DJANGO_API_KEY` = `resolvemeq-agent-secret-key-2026`
3. Trigger workflow or push changes

---

## 🧪 Testing After Configuration

### 1. Test Agent Health
```bash
curl https://agent.resolvemeq.net/health
```

Expected response should include:
```json
{
  "status": "healthy",
  "services": {
    "django_backend_url": "https://resolvemeq.net"
  }
}
```

### 2. Test Full Communication Flow

From Django project directory:
```bash
python test_full_communication.py
```

### 3. Test Ticket Processing

```bash
# Create a test ticket and trigger agent processing
python manage.py shell
```

```python
from tickets.models import Ticket
from base.models import User
from tickets.views import process_with_agent
from django.test import RequestFactory

# Create test user
user = User.objects.first()

# Create test ticket
ticket = Ticket.objects.create(
    user=user,
    issue_type="Test agent callback",
    description="Testing bidirectional communication",
    category="other"
)

# Process with agent (simulate API request)
factory = RequestFactory()
request = factory.post(f'/api/tickets/{ticket.ticket_id}/process/')
request.user = user

# This should now work without 500 error
response = process_with_agent(request, ticket.ticket_id)
print(response.data)
```

### 4. Monitor Celery Logs

```bash
tail -f /tmp/celery-worker.log | grep -A 3 "Sending POST to FastAPI"
```

Expected output:
```
Sending POST to FastAPI: https://agent.resolvemeq.net/tickets/analyze/
Received response from FastAPI: 200 {"status": "success", ...}
✅ Task completed successfully
```

---

## 🔍 Verification Checklist

- [ ] Agent has `DJANGO_BACKEND_URL` environment variable set
- [ ] Agent has `DJANGO_API_KEY` or `AGENT_API_KEY` environment variable set
- [ ] Agent code sends `X-Agent-API-Key` header in Django callbacks
- [ ] Agent service restarted after configuration
- [ ] Health check shows Django backend URL
- [ ] Test ticket processes successfully (no 500 error)
- [ ] Celery logs show successful agent responses
- [ ] Ticket status updates in Django database

---

## 📋 Expected Endpoints on Agent

The agent should implement these callback functions:

1. **Update Ticket Status**
```
POST {DJANGO_BACKEND_URL}/api/tickets/{ticket_id}/status/
Headers: X-Agent-API-Key: {DJANGO_API_KEY}
Body: {"status": "in-progress" | "resolved" | "pending"}
```

2. **Store Agent Response**
```
PATCH {DJANGO_BACKEND_URL}/api/tickets/{ticket_id}/
Headers: X-Agent-API-Key: {DJANGO_API_KEY}
Body: {
  "agent_response": "AI-generated solution...",
  "agent_processed": true,
  "status": "resolved"
}
```

---

## 🔐 Security Notes

- The API key `resolvemeq-agent-secret-key-2026` is a shared secret
- For production, generate a stronger key:
  ```bash
  python -c "import secrets; print(secrets.token_urlsafe(32))"
  ```
- Update in **both** Django and Agent environments
- Store in environment variables, **never** hardcode
- Rotate periodically for security

---

## 🆘 Troubleshooting

### Agent still returning 500?

1. **Check agent logs:**
```bash
# If using Docker
docker logs agent-container --tail 100

# If using systemd
journalctl -u agent-service -n 100
```

2. **Verify environment variables loaded:**
```bash
# On agent server
echo $DJANGO_BACKEND_URL
echo $DJANGO_API_KEY
```

3. **Test Django endpoint directly from agent server:**
```bash
curl -X POST https://resolvemeq.net/api/tickets/1/status/ \
  -H "Content-Type: application/json" \
  -H "X-Agent-API-Key: resolvemeq-agent-secret-key-2026" \
  -d '{"status": "in-progress"}'
```

Expected: `200 OK` with `{"message": "Ticket status updated to in-progress."}`

### Django rejecting agent requests?

1. **Check CSRF_TRUSTED_ORIGINS:**
```bash
python manage.py shell
```
```python
from django.conf import settings
print(settings.CSRF_TRUSTED_ORIGINS)
# Should include: https://agent.resolvemeq.net
```

2. **Verify AGENT_API_KEY:**
```python
print(settings.AGENT_API_KEY)
# Should be: resolvemeq-agent-secret-key-2026
```

---

## 📞 Next Steps

1. **Contact agent server administrator** or **check agent repository**
2. Add the two required environment variables
3. Restart agent service
4. Run test_full_communication.py
5. Verify ticket processing works end-to-end

Once configured, the full cycle should work:
```
User creates ticket → Django queues Celery task → Celery sends to Agent → 
Agent processes → Agent updates Django → Ticket marked as processed ✅
```

---

**Last Updated:** March 4, 2026  
**Status:** Django ✅ Complete | Agent ⚠️ Needs Configuration
