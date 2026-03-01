# Agent API Key Authentication Configuration

## Summary of Changes

### 1. CSRF Trusted Origins
Added `https://agent.resolvemeq.net` to `CSRF_TRUSTED_ORIGINS` in settings.py

### 2. Agent API Key Authentication
Created `AgentAPIKeyAuthentication` class in `base/authentication.py` that:
- Accepts `X-Agent-API-Key` header from requests
- Validates against configured API key
- Allows agent to authenticate without user credentials

### 3. Custom Permission
Created `IsAuthenticatedOrAgent` permission in `base/permissions.py` that:
- Allows authenticated users (via JWT)
- Also allows AI Agent with valid API key
- Applied to endpoints that agent needs to access

### 4. Updated Endpoints
Updated `update_ticket_status` endpoint to:
- Accept `IsAuthenticatedOrAgent` permission
- Handle both user and agent authentication
- Properly log who made the status change

### 5. REST Framework Configuration
Added `AgentAPIKeyAuthentication` to `DEFAULT_AUTHENTICATION_CLASSES`

## Configuration

### Django Side (✅ Complete)
```python
# In settings.py
AGENT_API_KEY = 'resolvemeq-agent-secret-key-2026'

# Added to CSRF_TRUSTED_ORIGINS
"https://agent.resolvemeq.net"
```

### Agent Side (⚠️ Needs Configuration)
The AI Agent needs to send this header with all requests to Django:

```python
headers = {
    'Content-Type': 'application/json',
    'X-Agent-API-Key': 'resolvemeq-agent-secret-key-2026'
}
```

## Environment Variables

### For Django (Production)
```bash
AGENT_API_KEY=resolvemeq-agent-secret-key-2026
```

### For Agent (Production)
```bash
DJANGO_API_KEY=resolvemeq-agent-secret-key-2026
# or
AGENT_API_KEY=resolvemeq-agent-secret-key-2026
```

## Testing

Run the test script:
```bash
python3 test_agent_auth.py
```

## Endpoints That Accept Agent Auth

1. `POST /api/tickets/<ticket_id>/status/` - Update ticket status
2. Any other endpoint decorated with `@permission_classes([IsAuthenticatedOrAgent])`

## Security Notes

- The API key is a shared secret between Django and the Agent
- Should be stored in environment variables, not hardcoded
- Can be rotated by updating `AGENT_API_KEY` in both services
- Different from user JWT tokens (agent doesn't need user context)

## Next Steps

1. ✅ Django configuration complete
2. ⚠️  Configure agent to send `X-Agent-API-Key` header
3. ⚠️  Deploy changes to production
4. ⚠️  Test full ticket analysis flow
5. ⚠️  Update agent environment variables
