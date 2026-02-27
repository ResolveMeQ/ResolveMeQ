# Deployment Guide: Trust & Reliability Improvements

**Version:** 2.0  
**Date:** February 27, 2026

---

## Quick Start

This guide covers deploying the newly implemented trust and reliability improvements to production.

---

## Pre-Deployment Checklist

- [ ] Review [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)
- [ ] Review [PLATFORM_ASSESSMENT.md](PLATFORM_ASSESSMENT.md)
- [ ] Sentry account created and project configured
- [ ] Staging environment tested
- [ ] Database backup completed
- [ ] Team notified of new features

---

## Step 1: Backend Deployment

### 1.1 Update Dependencies

```bash
cd /path/to/ResolveMeQ
source venv/bin/activate
pip install -r requirements.txt
```

**New packages installed:**
- `sentry-sdk==1.40.0` - Error monitoring
- `django-ratelimit==4.1.0` - Rate limiting

### 1.2 Set Environment Variables

Add to your `.env` file or environment:

```bash
# Sentry Monitoring (REQUIRED)
SENTRY_DSN=https://your-sentry-key@o123456.ingest.sentry.io/123456
ENVIRONMENT=production
APP_VERSION=2.0.0

# Agent Rate Limiting (OPTIONAL - defaults shown)
MAX_AUTONOMOUS_ACTIONS_PER_DAY=500
MAX_AUTONOMOUS_ACTIONS_PER_HOUR=100
```

**Get Sentry DSN:**
1. Go to [sentry.io](https://sentry.io)
2. Create account (free tier available)
3. Create new Django project
4. Copy DSN from Settings → Client Keys (DSN)

### 1.3 Run Database Migrations

```bash
python manage.py migrate
```

**Expected output:**
```
Applying tickets.0002_actionhistory_ticketresolution... OK
```

### 1.4 Verify Django Configuration

```bash
python manage.py check
```

Should show: `System check identified no issues (0 silenced).`

### 1.5 Collect Static Files

```bash
python manage.py collectstatic --noinput
```

### 1.6 Restart Services

```bash
# Restart Gunicorn/Django
sudo systemctl restart resolvemeq

# Restart Celery Workers
sudo systemctl restart resolvemeq-celery

# Restart Celery Beat
sudo systemctl restart resolvemeq-celerybeat
```

---

## Step 2: Sentry Alert Configuration

### 2.1 Configure Alerts

In Sentry dashboard, create these alerts:

**Alert 1: Autonomous Action Failures**
- Alert Name: "High Agent Action Failure Rate"
- Condition: Error rate > 10% in 1 hour for tag `component:autonomous_agent`
- Action: Send to Slack #resolvemeq-alerts

**Alert 2: Low Confidence Trend**
- Alert Name: "Low Agent Confidence"
- Condition: Custom metric `agent.confidence` < 0.5 average over 1 hour
- Action: Send to Slack #resolvemeq-alerts

**Alert 3: Agent API Errors**
- Alert Name: "Agent API Down"
- Condition: > 5 errors in 5 minutes
- Action: Send to Slack #resolvemeq-critical, Email on-call team

**Alert 4: High Rollback Rate**
- Alert Name: "Excessive Rollbacks"
- Condition: > 20 rollback events in 1 hour
- Action: Send to Slack #resolvemeq-alerts

### 2.2 Verify Sentry Integration

Test error capture:

```python
python manage.py shell

>>> from sentry_sdk import capture_message
>>> capture_message("Test deployment - Sentry is working!", level="info")
```

Check Sentry dashboard for the test message.

---

## Step 3: Frontend Deployment

### 3.1 Install Dependencies (if needed)

```bash
cd resolvemeqwebapp
npm install
```

### 3.2 Build for Production

```bash
npm run build
```

### 3.3 Deploy to Azure Static Web Apps

```bash
# Azure Static Web Apps automatically deploys on git push
git add .
git commit -m "Add trust & reliability improvements"
git push origin main
```

Or use Azure CLI:

```bash
az staticwebapp deploy \
  --name resolvemeq-webapp \
  --resource-group resolvemeq-rg \
  --app-location "./resolvemeqwebapp"
```

---

## Step 4: Testing in Production

### 4.1 Test Monitoring

Create a test ticket and verify Sentry tracking:

```bash
curl -X POST https://api.resolvemeq.com/api/tickets/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "issue_type": "Test for monitoring",
    "description": "Testing Sentry integration",
    "category": "other"
  }'
```

Check Sentry for event tracking.

### 4.2 Test Feedback Loop

1. Create a ticket and trigger auto-resolve
2. Wait 24 hours (or modify countdown in code for testing)
3. Verify follow-up scheduled in Celery
4. Submit feedback via API:

```bash
curl -X POST https://api.resolvemeq.com/api/tickets/123/resolution-feedback/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "resolution_confirmed": true,
    "satisfaction_score": 5,
    "feedback_text": "Works perfectly!"
  }'
```

### 4.3 Test Rollback (Admin Only)

1. Find an action history UUID:

```bash
curl https://api.resolvemeq.com/api/tickets/123/action-history/ \
  -H "Authorization: Bearer ADMIN_TOKEN"
```

2. Rollback the action:

```bash
curl -X POST https://api.resolvemeq.com/api/tickets/actions/{uuid}/rollback/ \
  -H "Authorization: Bearer ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"reason": "Testing rollback functionality"}'
```

3. Verify ticket status reverted.

### 4.4 Test Rate Limiting

Trigger 60 agent actions in 1 minute (should throttle at 50):

```bash
for i in {1..60}; do
  curl -X POST https://api.resolvemeq.com/api/tickets/$i/process/ \
    -H "Authorization: Bearer YOUR_TOKEN" &
done
```

Should receive HTTP 429 (Too Many Requests) after 50 requests.

### 4.5 View Analytics

```bash
curl https://api.resolvemeq.com/api/tickets/resolution-analytics/ \
  -H "Authorization: Bearer YOUR_TOKEN"
```

Should return:
```json
{
  "total_resolutions": 0,
  "confirmed_successful": 0,
  "confirmed_failed": 0,
  "reopened_tickets": 0,
  "average_satisfaction_score": null,
  "success_rate": 0,
  "action_type_breakdown": []
}
```

---

## Step 5: Frontend Features Verification

### 5.1 Verify Action History Component

1. Navigate to a ticket detail page
2. Should see "Autonomous Action History" section
3. Click "Rollback" button (admin only)
4. Confirm rollback modal appears

### 5.2 Verify Resolution Feedback Component

1. Navigate to a resolved ticket
2. Should see "How did we do?" feedback form
3. Click thumbs up/down
4. Rate with stars
5. Submit feedback
6. Should show "Thank you" message

### 5.3 Verify Resolution Analytics

1. Navigate to Analytics page
2. Should see "Resolution Analytics" section
3. Displays:
   - Total resolutions
   - Success rate
   - Average satisfaction
   - Reopened tickets count

---

## Step 6: Gradual Rollout

### Week 1: Monitor Only (10% of tickets)

```python
# In tickets/autonomous_agent.py, temporarily add:
import random

def decide_autonomous_action(self):
    # Only process 10% of tickets
    if random.random() > 0.1:
        return AgentAction.REQUEST_CLARIFICATION, {}
    
    # Normal logic...
```

**Monitor:**
- Sentry error rates
- False positive resolutions
- Rollback frequency
- User satisfaction scores

### Week 2: Increase to 50%

```python
if random.random() > 0.5:
    return AgentAction.REQUEST_CLARIFICATION, {}
```

**Monitor:**
- Resolution success rate
- Average confidence scores
- Ticket reopening rate

### Week 3: Full Rollout (100%)

Remove the random check. Monitor for 1 week before declaring success.

---

## Step 7: Post-Deployment Monitoring

### Daily Checks (First Week)

1. **Sentry Dashboard**
   - Check error count (should be < 5/hour)
   - Review low confidence alerts
   - Check agent API uptime

2. **Resolution Analytics**
   - Success rate should be > 80%
   - Average satisfaction should be > 4.0
   - Reopened tickets should be < 5%

3. **Action History**
   - Review rollback frequency (should be < 1%)
   - Check rollback reasons for patterns

### Weekly Reports

Generate weekly report:

```bash
curl https://api.resolvemeq.com/api/tickets/agent/analytics/ \
  -H "Authorization: Bearer YOUR_TOKEN" > weekly_report.json

curl https://api.resolvemeq.com/api/tickets/resolution-analytics/ \
  -H "Authorization: Bearer YOUR_TOKEN" >> weekly_report.json
```

**Key Metrics:**
- Agent processing rate: Target 30-50%
- Resolution success rate: Target > 85%
- Average confidence: Target > 0.7
- Average satisfaction: Target > 4.0

---

## Troubleshooting

### Issue: Sentry not receiving events

**Check:**
1. SENTRY_DSN is set correctly
2. Sentry project is active
3. Test with: `python manage.py shell` → `from sentry_sdk import capture_message; capture_message("test")`

### Issue: Follow-ups not being sent

**Check:**
1. Celery beat is running: `sudo systemctl status resolvemeq-celerybeat`
2. Check Celery worker logs: `sudo journalctl -u resolvemeq-celery -f`
3. Verify Redis is accessible

### Issue: Rate limiting too aggressive

**Adjust in settings.py:**
```python
'DEFAULT_THROTTLE_RATES': {
    'agent_actions': '100/minute',  # Increased from 50
}
```

### Issue: Rollback not working

**Check:**
1. User has admin permissions
2. Action has `rollback_possible=True`
3. Action not already rolled back
4. Check logs for specific error

---

## Rollback Plan (Emergency)

If critical issues arise:

### 1. Disable Autonomous Actions

```python
# In tickets/tasks.py, temporarily add at top of execute_autonomous_action:
return False  # Disable all autonomous actions
```

Restart Celery: `sudo systemctl restart resolvemeq-celery`

### 2. Revert Database Migration

```bash
python manage.py migrate tickets 0001
```

**Warning:** This will lose ActionHistory and TicketResolution data!

### 3. Revert Code

```bash
git revert HEAD
git push
```

### 4. Notify Team

Send alert to #resolvemeq-critical with:
- Issue description
- Impact assessment
- Rollback actions taken
- ETA for fix

---

## Success Criteria

Deployment is successful when:

- ✅ No critical errors in Sentry (first 24 hours)
- ✅ Resolution success rate > 80%
- ✅ Average satisfaction score > 4.0
- ✅ Rollback rate < 2%
- ✅ Follow-ups being sent (check Celery logs)
- ✅ Rate limiting working (test with 60 requests)
- ✅ Frontend components displaying correctly

---

## Support

**Questions?** Contact:
- DevOps: devops@resolvemeq.com
- Product: product@resolvemeq.com
- Slack: #resolvemeq-support

**Documentation:**
- [PLATFORM_ASSESSMENT.md](PLATFORM_ASSESSMENT.md)
- [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)
- [QUICK_START_IMPROVEMENTS.md](QUICK_START_IMPROVEMENTS.md)

---

**Deployed by:** _________________  
**Date:** _________________  
**Status:** ☐ Success  ☐ Rollback  ☐ Partial
