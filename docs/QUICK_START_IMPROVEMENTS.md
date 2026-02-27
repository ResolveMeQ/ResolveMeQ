# Quick Start: Critical Improvements Implementation Guide

**Goal:** Achieve production readiness in 2 weeks by implementing the top 3 critical improvements.

---

## Week 1: Days 1-3 - Real-Time Monitoring

### Step 1: Install Sentry (Day 1)

```bash
# Add to requirements.txt
echo "sentry-sdk==1.40.0" >> requirements.txt
pip install sentry-sdk
```

### Step 2: Configure Sentry (Day 1)

Create account at [sentry.io](https://sentry.io) (free tier: 5k errors/month)

```python
# Add to resolvemeq/settings.py (after imports)
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.celery import CeleryIntegration

# Sentry Configuration
SENTRY_DSN = os.getenv('SENTRY_DSN', '')
if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[
            DjangoIntegration(),
            CeleryIntegration(),
        ],
        traces_sample_rate=0.1,  # 10% of transactions
        profiles_sample_rate=0.1,
        environment=os.getenv('ENVIRONMENT', 'production'),
        release=os.getenv('APP_VERSION', '2.0.0'),
        
        # Filter out sensitive data
        before_send=lambda event, hint: None if 'password' in str(event).lower() else event,
    )
```

### Step 3: Add Custom Metrics (Days 2-3)

```python
# Create monitoring/metrics.py
from sentry_sdk import capture_message, capture_exception
import logging

logger = logging.getLogger(__name__)

class AgentMetrics:
    """Track autonomous agent performance metrics"""
    
    @staticmethod
    def track_autonomous_action(action_type, ticket_id, confidence, success):
        """Log autonomous action with context"""
        from sentry_sdk import set_tag, set_context
        
        set_tag("action_type", action_type)
        set_tag("success", success)
        set_context("agent_action", {
            "ticket_id": ticket_id,
            "confidence": confidence,
            "action_type": action_type,
        })
        
        if not success:
            capture_message(
                f"Autonomous action failed: {action_type}",
                level="warning"
            )
    
    @staticmethod
    def track_agent_error(error, ticket_id):
        """Capture agent processing errors"""
        from sentry_sdk import set_tag, set_context
        
        set_tag("component", "autonomous_agent")
        set_context("ticket", {"ticket_id": ticket_id})
        capture_exception(error)
```

### Step 4: Integrate Metrics in Tasks (Day 3)

```python
# Update tickets/tasks.py
from monitoring.metrics import AgentMetrics

@app.task
def execute_autonomous_action(ticket_id, action, params):
    """Execute the autonomous action decided by the agent."""
    success = False
    try:
        ticket = Ticket.objects.get(ticket_id=ticket_id)
        confidence = ticket.agent_response.get('confidence', 0.0)
        
        logger.info(f"Executing autonomous action {action} for ticket {ticket_id}")
        
        if action == AgentAction.AUTO_RESOLVE.value:
            success = handle_auto_resolve(ticket, params)
        elif action == AgentAction.ESCALATE.value:
            success = handle_escalate(ticket, params)
        # ... other actions
        
        # Track the action
        AgentMetrics.track_autonomous_action(action, ticket_id, confidence, success)
        
        return success
            
    except Exception as e:
        AgentMetrics.track_agent_error(e, ticket_id)
        logger.error(f"Error executing autonomous action: {str(e)}")
        raise
```

### Step 5: Set Up Alerts (Day 3)

In Sentry dashboard:
1. Create alert rule: "Autonomous action failure rate > 10% in 1 hour"
2. Create alert rule: "Agent API errors > 5 in 5 minutes"
3. Create alert rule: "Low confidence trend (avg < 0.5 in 1 hour)"
4. Configure Slack notifications to #resolvemeq-alerts channel

---

## Week 1: Days 4-7 - Feedback Loop Validation

### Step 1: Create Models (Day 4)

```python
# Add to tickets/models.py

class TicketResolution(models.Model):
    """Track resolution outcomes for learning and validation"""
    
    ticket = models.OneToOneField(
        Ticket, 
        on_delete=models.CASCADE,
        related_name='resolution_tracking'
    )
    autonomous_action = models.CharField(max_length=50)
    
    # User Feedback
    resolution_confirmed = models.BooleanField(null=True, blank=True)
    user_feedback_text = models.TextField(blank=True)
    satisfaction_score = models.IntegerField(
        null=True, 
        blank=True,
        help_text="1-5 stars"
    )
    
    # Follow-up
    followup_sent_at = models.DateTimeField(null=True, blank=True)
    response_received_at = models.DateTimeField(null=True, blank=True)
    
    # Reopening
    reopened = models.BooleanField(default=False)
    reopened_at = models.DateTimeField(null=True, blank=True)
    reopened_reason = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'ticket_resolution'
        indexes = [
            models.Index(fields=['autonomous_action', 'resolution_confirmed']),
        ]
    
    @property
    def was_successful(self):
        """Did this resolution actually work?"""
        if self.reopened:
            return False
        if self.resolution_confirmed is True:
            return True
        if self.satisfaction_score and self.satisfaction_score >= 4:
            return True
        return None  # Unknown
```

Run migration:
```bash
python manage.py makemigrations
python manage.py migrate
```

### Step 2: Create Follow-up Task (Day 5)

```python
# Update tickets/tasks.py

@app.task
def schedule_resolution_followup(ticket_id):
    """
    Send follow-up message 24 hours after auto-resolve to verify success.
    """
    try:
        ticket = Ticket.objects.get(ticket_id=ticket_id)
        
        # Create resolution tracking if not exists
        resolution, created = TicketResolution.objects.get_or_create(
            ticket=ticket,
            defaults={
                'autonomous_action': ticket.agent_response.get('recommended_action', 'unknown')
            }
        )
        
        if resolution.followup_sent_at:
            logger.info(f"Follow-up already sent for ticket {ticket_id}")
            return
        
        # Send Slack message with interactive buttons
        from integrations.views import send_slack_message
        
        message = {
            "channel": ticket.user.slack_user_id,
            "text": f"📋 Follow-up: Ticket #{ticket.ticket_id}",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"Hi! We marked your ticket *#{ticket.ticket_id}* as resolved yesterday.\n\n*Was your issue actually resolved?*"
                    }
                },
                {
                    "type": "actions",
                    "block_id": f"resolution_feedback_{ticket_id}",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "✅ Yes, it works!"},
                            "style": "primary",
                            "value": f"confirmed_{ticket_id}",
                            "action_id": "confirm_resolution"
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "❌ No, still broken"},
                            "style": "danger",
                            "value": f"failed_{ticket_id}",
                            "action_id": "reject_resolution"
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "🤔 Partially fixed"},
                            "value": f"partial_{ticket_id}",
                            "action_id": "partial_resolution"
                        }
                    ]
                }
            ]
        }
        
        send_slack_message(message)
        
        resolution.followup_sent_at = timezone.now()
        resolution.save()
        
        logger.info(f"Follow-up sent for ticket {ticket_id}")
        
    except Exception as e:
        logger.error(f"Error sending follow-up for ticket {ticket_id}: {str(e)}")
        raise


def handle_auto_resolve(ticket, params):
    """
    Enhanced auto-resolve with follow-up scheduling.
    """
    resolution_steps = params.get("resolution_steps", "No steps provided")
    
    # Mark ticket as resolved
    ticket.status = "resolved"
    ticket.save()
    
    # Create interaction
    TicketInteraction.objects.create(
        ticket=ticket,
        user=ticket.user,
        interaction_type="agent_response",
        content=f"Auto-resolved by AI agent.\n\nResolution:\n{resolution_steps}"
    )
    
    # Send notification to user
    from integrations.views import notify_user_agent_response
    notify_user_agent_response(ticket, ticket.agent_response)
    
    # --- NEW: Schedule 24-hour follow-up ---
    from datetime import timedelta
    schedule_resolution_followup.apply_async(
        args=[ticket.ticket_id],
        countdown=86400  # 24 hours in seconds
    )
    
    logger.info(f"Ticket {ticket.ticket_id} auto-resolved and follow-up scheduled")
    return True
```

### Step 3: Create Slack Interaction Handlers (Days 6-7)

```python
# Add to integrations/views.py

@csrf_exempt
def slack_interactivity(request):
    """Handle Slack interactive components (buttons, modals)"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid method'}, status=405)
    
    # Parse payload
    payload = json.loads(request.POST.get('payload'))
    action = payload['actions'][0]
    action_id = action['action_id']
    value = action['value']
    user_id = payload['user']['id']
    
    if action_id == 'confirm_resolution':
        # User confirmed resolution worked
        ticket_id = int(value.split('_')[1])
        ticket = Ticket.objects.get(ticket_id=ticket_id)
        
        resolution = TicketResolution.objects.get(ticket=ticket)
        resolution.resolution_confirmed = True
        resolution.response_received_at = timezone.now()
        resolution.satisfaction_score = 5
        resolution.save()
        
        # Update Slack message
        return JsonResponse({
            'text': f'✅ Great! Ticket #{ticket_id} is confirmed resolved. Thank you for the feedback!'
        })
    
    elif action_id == 'reject_resolution':
        # User says issue NOT resolved - reopen ticket
        ticket_id = int(value.split('_')[1])
        ticket = Ticket.objects.get(ticket_id=ticket_id)
        
        resolution = TicketResolution.objects.get(ticket=ticket)
        resolution.resolution_confirmed = False
        resolution.response_received_at = timezone.now()
        resolution.reopened = True
        resolution.reopened_at = timezone.now()
        resolution.satisfaction_score = 1
        resolution.save()
        
        # Reopen ticket and assign to human
        ticket.status = 'escalated'
        ticket.save()
        
        # Notify IT team
        send_slack_message({
            'channel': settings.IT_TEAM_CHANNEL,
            'text': f'⚠️ Auto-resolved ticket #{ticket_id} was NOT actually resolved. User needs help.'
        })
        
        return JsonResponse({
            'text': f'❌ Sorry to hear that! Ticket #{ticket_id} has been reopened and escalated to our IT team.'
        })
    
    elif action_id == 'partial_resolution':
        # Partial success
        ticket_id = int(value.split('_')[1])
        ticket = Ticket.objects.get(ticket_id=ticket_id)
        
        resolution = TicketResolution.objects.get(ticket=ticket)
        resolution.resolution_confirmed = False
        resolution.response_received_at = timezone.now()
        resolution.satisfaction_score = 3
        resolution.save()
        
        ticket.status = 'in-progress'
        ticket.save()
        
        return JsonResponse({
            'text': f'🤔 Got it. Ticket #{ticket_id} is back in progress. An agent will follow up soon.'
        })
    
    return JsonResponse({'ok': True})


# Update integrations/urls.py
urlpatterns = [
    # ... existing patterns
    path('slack/interactivity/', slack_interactivity, name='slack-interactivity'),
]
```

In Slack App settings (api.slack.com/apps):
- Enable "Interactivity & Shortcuts"
- Set Request URL: `https://your-domain.com/api/integrations/slack/interactivity/`

---

## Week 2: Days 8-10 - Rollback Mechanism

### Step 1: Create ActionHistory Model (Day 8)

```python
# Add to tickets/models.py

class ActionHistory(models.Model):
    """
    Audit trail for all autonomous actions with rollback capability.
    Enables compliance, debugging, and recovery from incorrect agent decisions.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='action_history')
    
    # Action Details
    action_type = models.CharField(max_length=50)  # AUTO_RESOLVE, ESCALATE, etc.
    action_params = models.JSONField(default=dict)
    executed_at = models.DateTimeField(auto_now_add=True)
    executed_by = models.CharField(max_length=50, default='autonomous_agent')
    
    # AI Decision Context
    confidence_score = models.FloatField(null=True, blank=True)
    agent_reasoning = models.TextField(blank=True)
    
    # Rollback Capability
    rollback_possible = models.BooleanField(default=False)
    rollback_steps = models.JSONField(null=True, blank=True)
    rolled_back = models.BooleanField(default=False)
    rolled_back_at = models.DateTimeField(null=True, blank=True)
    rolled_back_by = models.ForeignKey(
        User, 
        null=True, 
        blank=True,
        on_delete=models.SET_NULL,
        related_name='rollbacks_performed'
    )
    rollback_reason = models.TextField(blank=True)
    
    # State Snapshots
    before_state = models.JSONField(null=True, blank=True)
    after_state = models.JSONField(null=True, blank=True)
    
    class Meta:
        db_table = 'action_history'
        ordering = ['-executed_at']
        indexes = [
            models.Index(fields=['ticket', 'action_type']),
            models.Index(fields=['executed_at']),
            models.Index(fields=['rolled_back']),
        ]
    
    def __str__(self):
        return f"{self.action_type} on Ticket #{self.ticket.ticket_id} at {self.executed_at}"
```

Run migration:
```bash
python manage.py makemigrations
python manage.py migrate
```

### Step 2: Create Rollback Handlers (Days 9-10)

```python
# Create tickets/rollback.py

from django.utils import timezone
from .models import Ticket, ActionHistory, TicketInteraction
import logging

logger = logging.getLogger(__name__)

class RollbackManager:
    """Manage rollback of autonomous actions"""
    
    @staticmethod
    def rollback_auto_resolve(ticket, action_history, rollback_by, reason):
        """Revert an AUTO_RESOLVE action"""
        try:
            # Restore previous state
            if action_history.before_state:
                ticket.status = action_history.before_state.get('status', 'in-progress')
            else:
                ticket.status = 'in-progress'
            
            ticket.save()
            
            # Add interaction explaining rollback
            TicketInteraction.objects.create(
                ticket=ticket,
                user=rollback_by,
                interaction_type='agent_response',
                content=f"Auto-resolution was rolled back. Reason: {reason}"
            )
            
            # Mark action as rolled back
            action_history.rolled_back = True
            action_history.rolled_back_at = timezone.now()
            action_history.rolled_back_by = rollback_by
            action_history.rollback_reason = reason
            action_history.save()
            
            logger.info(f"Rolled back AUTO_RESOLVE for ticket {ticket.ticket_id}")
            return True
            
        except Exception as e:
            logger.error(f"Rollback failed: {str(e)}")
            return False
    
    @staticmethod
    def rollback_assign_to_team(ticket, action_history, rollback_by, reason):
        """Revert team assignment"""
        try:
            # Restore previous assignment
            if action_history.before_state:
                prev_assignee = action_history.before_state.get('assigned_to_id')
                if prev_assignee:
                    from base.models import User
                    ticket.assigned_to = User.objects.get(user_id=prev_assignee)
                else:
                    ticket.assigned_to = None
            
            ticket.save()
            
            action_history.rolled_back = True
            action_history.rolled_back_at = timezone.now()
            action_history.rolled_back_by = rollback_by
            action_history.rollback_reason = reason
            action_history.save()
            
            logger.info(f"Rolled back team assignment for ticket {ticket.ticket_id}")
            return True
            
        except Exception as e:
            logger.error(f"Rollback failed: {str(e)}")
            return False
    
    @staticmethod
    def can_rollback(action_type):
        """Check if action type supports rollback"""
        ROLLBACK_SUPPORTED = [
            'AUTO_RESOLVE',
            'ASSIGN_TO_TEAM',
            'SCHEDULE_FOLLOWUP',
        ]
        return action_type in ROLLBACK_SUPPORTED
```

### Step 3: Update Action Handlers to Record History (Day 10)

```python
# Update tickets/tasks.py

def handle_auto_resolve(ticket, params):
    """Enhanced auto-resolve with action history"""
    
    # Capture state before action
    before_state = {
        'status': ticket.status,
        'assigned_to_id': ticket.assigned_to.user_id if ticket.assigned_to else None,
    }
    
    resolution_steps = params.get("resolution_steps", "No steps provided")
    confidence = ticket.agent_response.get('confidence', 0.0)
    
    # Execute action
    ticket.status = "resolved"
    ticket.save()
    
    # Capture state after action
    after_state = {
        'status': ticket.status,
        'assigned_to_id': ticket.assigned_to.user_id if ticket.assigned_to else None,
    }
    
    # Record action in history
    ActionHistory.objects.create(
        ticket=ticket,
        action_type='AUTO_RESOLVE',
        action_params=params,
        confidence_score=confidence,
        agent_reasoning=ticket.agent_response.get('explanation', ''),
        rollback_possible=True,
        rollback_steps={'handler': 'rollback_auto_resolve'},
        before_state=before_state,
        after_state=after_state,
    )
    
    # ... rest of resolution logic
    
    return True
```

### Step 4: Create Rollback API Endpoint (Day 10)

```python
# Add to tickets/views.py

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def rollback_action(request, action_history_id):
    """
    Rollback an autonomous action (admin/manager only).
    """
    from tickets.rollback import RollbackManager
    from tickets.models import ActionHistory
    
    # Check permissions
    if not request.user.is_staff and not request.user.role == 'manager':
        return Response(
            {'error': 'Only admins and managers can rollback actions'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        action_history = ActionHistory.objects.get(id=action_history_id)
        
        if action_history.rolled_back:
            return Response(
                {'error': 'This action was already rolled back'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not RollbackManager.can_rollback(action_history.action_type):
            return Response(
                {'error': f'Action type {action_history.action_type} does not support rollback'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        reason = request.data.get('reason', 'Manual rollback by admin')
        
        # Execute rollback
        if action_history.action_type == 'AUTO_RESOLVE':
            success = RollbackManager.rollback_auto_resolve(
                action_history.ticket,
                action_history,
                request.user,
                reason
            )
        elif action_history.action_type == 'ASSIGN_TO_TEAM':
            success = RollbackManager.rollback_assign_to_team(
                action_history.ticket,
                action_history,
                request.user,
                reason
            )
        else:
            return Response(
                {'error': 'Rollback handler not implemented'},
                status=status.HTTP_501_NOT_IMPLEMENTED
            )
        
        if success:
            return Response({
                'message': 'Action rolled back successfully',
                'ticket_id': action_history.ticket.ticket_id,
                'action_type': action_history.action_type,
            })
        else:
            return Response(
                {'error': 'Rollback failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
    except ActionHistory.DoesNotExist:
        return Response(
            {'error': 'Action history not found'},
            status=status.HTTP_404_NOT_FOUND
        )


# Add to tickets/urls.py
urlpatterns = [
    # ... existing patterns
    path('actions/<uuid:action_history_id>/rollback/', rollback_action, name='rollback-action'),
]
```

---

## Testing Your Improvements

### Test Monitoring (Day 11)
```bash
# Trigger an error to test Sentry
python manage.py shell
>>> from tickets.tasks import process_ticket_with_agent
>>> process_ticket_with_agent.delay(999999)  # Non-existent ticket
# Check Sentry dashboard for error report
```

### Test Feedback Loop (Day 12)
```bash
# Create a test ticket and auto-resolve
python manage.py shell
>>> from tickets.models import Ticket
>>> from base.models import User
>>> user = User.objects.first()
>>> ticket = Ticket.objects.create(
...     user=user,
...     issue_type='Can\'t log in',
...     description='Password reset needed',
...     category='account',
...     status='resolved'
... )
>>> from tickets.tasks import schedule_resolution_followup
>>> schedule_resolution_followup.delay(ticket.ticket_id)
# Check Slack for follow-up message in 24 hours (or set countdown=60 for testing)
```

### Test Rollback (Day 13)
```bash
# Use admin panel or API to rollback an action
curl -X POST https://your-domain.com/api/tickets/actions/{action_uuid}/rollback/ \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"reason": "Testing rollback functionality"}'
```

---

## Deployment Checklist

- [ ] Add SENTRY_DSN to environment variables
- [ ] Configure Slack interactivity endpoint
- [ ] Run migrations for new models
- [ ] Deploy monitoring code to production
- [ ] Test Sentry alerts in staging
- [ ] Test follow-up messages in staging
- [ ] Test rollback in staging
- [ ] Train support team on rollback procedures
- [ ] Update documentation

**Total Time:** ~13 days (2 weeks with buffer)  
**Result:** 95% production-ready platform with trust mechanisms in place
