from celery import shared_task
from celery.exceptions import MaxRetriesExceededError, Retry
from django.conf import settings
import requests
from .models import Ticket, ActionHistory, TicketResolution
import logging
from resolvemeq.celery import app
from integrations.views import notify_user_agent_response  # Restored import for Slack feedback
from solutions.models import Solution
from .autonomous_agent import AutonomousAgent, AgentAction
from .confidence_settings import agent_confidence_high
from .handoff import build_handoff_packet
from .outcome_helpers import apply_escalated_timestamp, log_agent_confidence_snapshot, touch_first_ai_at
from monitoring.metrics import AgentMetrics
from django.utils import timezone

from base.agent_http import get_agent_service_headers
from base.agent_usage import (
    get_billing_user_for_ticket,
    refund_agent_operation,
    try_consume_agent_operation,
)

logger = logging.getLogger(__name__)

@app.task(bind=True, max_retries=3)
def process_ticket_with_agent(self, ticket_id, thread_ts=None, force=False, billing_precharged=False):
    """
    Celery task to process a ticket with the AI agent.
    Now includes autonomous decision-making and actions.

    Args:
        ticket_id: ID of the ticket to process
        thread_ts: Slack thread timestamp (optional)
        force: If True, re-process even if already processed
        billing_precharged: If True, monthly quota was already charged (e.g. manual API trigger)
    """
    logger.info(
        f"Celery task started for ticket_id={ticket_id} (force={force}, billing_precharged={billing_precharged})"
    )
    billing_user = None
    agent_saved = False
    try:
        ticket = Ticket.objects.select_related("team", "team__owner", "user").get(ticket_id=ticket_id)
        billing_user = get_billing_user_for_ticket(ticket)

        if ticket.agent_processed and not force:
            logger.info(f"Ticket {ticket_id} already processed by agent (use force=True to re-process)")
            if billing_precharged:
                refund_agent_operation(billing_user)
            return False

        if not billing_precharged:
            quota = try_consume_agent_operation(billing_user)
            if not quota.allowed:
                logger.warning(
                    "Agent quota exceeded for user %s (ticket %s)", getattr(billing_user, "pk", billing_user), ticket_id
                )
                return False

        # Prepare the payload as expected by FastAPI
        payload = {
            "ticket_id": ticket.ticket_id,
            "issue_type": ticket.issue_type,
            "description": ticket.description,
            "category": ticket.category,
            "tags": ticket.tags,
            "user": {
                "id": str(ticket.user.id),
                "name": ticket.user.username,
                "department": getattr(ticket.user, "department", "")
            }
        }

        # Send to agent
        agent_url = getattr(settings, 'AI_AGENT_URL', 'https://agent.resolvemeq.com/api/analyze')
        headers = get_agent_service_headers()
        logger.info(f"Sending POST to FastAPI: {agent_url} with payload: {payload}")
        response = requests.post(agent_url, json=payload, headers=headers, timeout=30)
        logger.info(f"Received response from FastAPI: {response.status_code} {response.text}")
        response.raise_for_status()

        # Update ticket with agent response
        ticket.agent_response = response.json()
        ticket.agent_processed = True
        ticket.save()
        agent_saved = True

        touch_first_ai_at(ticket)
        if isinstance(ticket.agent_response, dict):
            log_agent_confidence_snapshot(
                ticket,
                "analyze",
                confidence=ticket.agent_response.get("confidence"),
                recommended_action=str(ticket.agent_response.get("recommended_action") or ""),
            )

        # --- NEW: Autonomous Agent Decision Making ---
        autonomous_agent = AutonomousAgent(ticket)
        action, params = autonomous_agent.decide_autonomous_action()

        logger.info(f"Autonomous agent decided: {action.value} for ticket {ticket_id}")

        # Execute the autonomous action
        execute_autonomous_action.delay(ticket_id, action.value, params)

        # --- Create Solution if agent provided steps or resolution ---
        agent_data = ticket.agent_response
        steps = None
        confidence = 0.0
        if isinstance(agent_data, dict):
            solution_data = agent_data.get("solution", {})
            steps = solution_data.get("steps") or agent_data.get("resolution_steps") or agent_data.get("steps")
            confidence = agent_data.get("confidence", 0.0)
            if steps and isinstance(steps, list):
                steps = "\n".join(steps)
            elif isinstance(steps, str):
                pass  # Already a string
        # Mark as solution if confidence is high
        if steps and confidence >= agent_confidence_high():
            Solution.objects.get_or_create(
                ticket=ticket,
                defaults={
                    "steps": steps,
                    "worked": True,
                    "created_by": ticket.user,
                    "confidence_score": confidence,
                }
            )
        elif steps:
            Solution.objects.get_or_create(
                ticket=ticket,
                defaults={
                    "steps": steps,
                    "worked": False,
                    "created_by": ticket.user,
                    "confidence_score": confidence,
                }
            )

        # --- Sync to knowledge base if ticket is resolved ---
        if ticket.status == "resolved":
            ticket.sync_to_knowledge_base()

        logger.info(f"Successfully processed ticket {ticket_id} with autonomous agent")

        return True

    except Retry:
        raise

    except requests.RequestException as exc:
        logger.error(f"Error processing ticket {ticket_id} with agent: {str(exc)}")
        try:
            self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
        except MaxRetriesExceededError:
            logger.error(f"Max retries exceeded for ticket {ticket_id}")
            if billing_user:
                refund_agent_operation(billing_user)
            return False

    except Ticket.DoesNotExist:
        logger.error(f"Ticket {ticket_id} not found")
        return False

    except Exception as e:
        logger.error(f"Unexpected error processing ticket {ticket_id}: {str(e)}")
        if billing_user and not agent_saved:
            refund_agent_operation(billing_user)
        return False

@app.task
def execute_autonomous_action(ticket_id, action, params):
    """
    Execute the autonomous action decided by the agent.
    Now includes action history tracking and metrics.
    """
    success = False
    try:
        ticket = Ticket.objects.get(ticket_id=ticket_id)
        confidence = ticket.agent_response.get('confidence', 0.0) if isinstance(ticket.agent_response, dict) else 0.0
        
        logger.info(f"Executing autonomous action {action} for ticket {ticket_id}")
        
        if action == AgentAction.AUTO_RESOLVE.value:
            success = handle_auto_resolve(ticket, params)
        elif action == AgentAction.ESCALATE.value:
            success = handle_escalate(ticket, params)
        elif action == AgentAction.REQUEST_CLARIFICATION.value:
            success = handle_request_clarification(ticket, params)
        elif action == AgentAction.ASSIGN_TO_TEAM.value:
            success = handle_assign_to_team(ticket, params)
        elif action == AgentAction.SCHEDULE_FOLLOWUP.value:
            success = handle_schedule_followup(ticket, params)
        elif action == AgentAction.CREATE_KB_ARTICLE.value:
            success = handle_create_kb_article(ticket, params)
        else:
            logger.warning(f"Unknown autonomous action: {action}")
            success = False
        
        # Track the action with monitoring
        AgentMetrics.track_autonomous_action(action, ticket_id, confidence, success)
        
        return success
            
    except Exception as e:
        # Track error with monitoring
        AgentMetrics.track_agent_error(e, ticket_id, {'action': action, 'params': params})
        logger.error(f"Error executing autonomous action {action} for ticket {ticket_id}: {str(e)}")
        return False

def handle_auto_resolve(ticket, params):
    """
    Automatically resolve the ticket.
    Enhanced with action history tracking and follow-up scheduling.
    """
    from integrations.views import notify_user_auto_resolution
    from tickets.models import TicketInteraction
    
    # Capture state before action
    before_state = {
        'status': ticket.status,
        'assigned_to_id': ticket.assigned_to.user_id if ticket.assigned_to else None,
    }
    
    resolution_steps = params.get("resolution_steps", "No steps provided")
    confidence = ticket.agent_response.get('confidence', 0.0) if isinstance(ticket.agent_response, dict) else 0.0
    reasoning = ticket.agent_response.get('explanation', '') if isinstance(ticket.agent_response, dict) else ''
    
    # Execute action
    ticket.status = "resolved"
    ticket.save()
    
    # Capture state after action
    after_state = {
        'status': ticket.status,
        'assigned_to_id': ticket.assigned_to.user_id if ticket.assigned_to else None,
    }
    
    # Record action in history for rollback capability
    ActionHistory.objects.create(
        ticket=ticket,
        action_type='AUTO_RESOLVE',
        action_params=params,
        confidence_score=confidence,
        agent_reasoning=reasoning,
        rollback_possible=True,
        rollback_steps={'handler': 'rollback_auto_resolve'},
        before_state=before_state,
        after_state=after_state,
    )
    
    # Create interaction record
    TicketInteraction.objects.create(
        ticket=ticket,
        user=ticket.user,
        interaction_type="agent_response",
        content=f"🤖 Auto-resolved by AI Agent.\n\nResolution:\n{resolution_steps}"
    )
    
    # Create resolution tracking for feedback loop
    TicketResolution.objects.get_or_create(
        ticket=ticket,
        defaults={'autonomous_action': 'AUTO_RESOLVE'}
    )
    
    # Notify user
    notify_user_auto_resolution(str(ticket.user.id), ticket.ticket_id, params)
    
    # Schedule 24-hour follow-up to verify resolution actually worked
    schedule_resolution_followup.apply_async(
        args=[ticket.ticket_id],
        countdown=86400  # 24 hours
    )
    
    logger.info(f"Auto-resolved ticket {ticket.ticket_id} with follow-up scheduled")
    return True

def handle_escalate(ticket, params):
    """Escalate the ticket to human support with action history."""
    from integrations.views import notify_escalation
    from tickets.models import TicketInteraction

    params = dict(params or {})
    
    # Capture state before
    before_state = {'status': ticket.status}
    
    ticket.status = "escalated"
    apply_escalated_timestamp(ticket)
    ticket.save()
    
    # Capture state after
    after_state = {'status': ticket.status}
    
    confidence = ticket.agent_response.get('confidence', 0.0) if isinstance(ticket.agent_response, dict) else 0.0
    reasoning = params.get('escalation_reason', 'Requires human attention')
    
    # Record action in history
    ActionHistory.objects.create(
        ticket=ticket,
        action_type='ESCALATE',
        action_params=params,
        confidence_score=confidence,
        agent_reasoning=reasoning,
        rollback_possible=True,
        rollback_steps={'handler': 'rollback_escalate'},
        before_state=before_state,
        after_state=after_state,
    )
    
    # Create interaction record
    TicketInteraction.objects.create(
        ticket=ticket,
        user=ticket.user,
        interaction_type="agent_response",
        content=f"⚠️ Escalated: {reasoning}"
    )
    
    packet = build_handoff_packet(
        ticket, ticket.user, params.get("conversation_summary", "")
    )
    params["handoff_text"] = packet["handoff_text"]
    params["handoff_summary"] = packet["handoff_summary"]

    # Notify user (Slack + in-app)
    notify_escalation(str(ticket.user.id), ticket.ticket_id, params)
    from .views import _notify_ticket_status_change
    _notify_ticket_status_change(ticket, "escalated")
    # Notify support staff (in-app + optional Slack channel)
    from .notifications import notify_support_escalation
    notify_support_escalation(ticket, params)

    logger.info(f"Escalated ticket {ticket.ticket_id}")
    return True

def handle_request_clarification(ticket, params):
    """Request clarification from user."""
    from integrations.views import request_clarification_from_user
    
    ticket.status = "pending_clarification"
    ticket.save()
    
    # Create interaction record
    from tickets.models import TicketInteraction
    TicketInteraction.objects.create(
        ticket=ticket,
        user=ticket.user,
        interaction_type="agent_clarification_request",
        content=f"Requested clarification: {params.get('reason', 'Need more information')}"
    )
    
    # Send clarification request to user
    request_clarification_from_user(str(ticket.user.id), ticket.ticket_id, params)
    
    logger.info(f"Requested clarification for ticket {ticket.ticket_id}")
    return True

def handle_assign_to_team(ticket, params):
    """Assign ticket to specific team with action history."""
    from tickets.models import TicketInteraction
    
    # Capture state before
    before_state = {
        'assigned_to_id': ticket.assigned_to.user_id if ticket.assigned_to else None,
        'status': ticket.status
    }
    
    assigned_team = params.get("assigned_team", "IT Support")
    ticket.status = "assigned"
    ticket.save()
    
    # Capture state after
    after_state = {
        'assigned_to_id': ticket.assigned_to.user_id if ticket.assigned_to else None,
        'status': ticket.status
    }
    
    confidence = ticket.agent_response.get('confidence', 0.0) if isinstance(ticket.agent_response, dict) else 0.0
    
    # Record action in history
    ActionHistory.objects.create(
        ticket=ticket,
        action_type='ASSIGN_TO_TEAM',
        action_params=params,
        confidence_score=confidence,
        agent_reasoning=f"Assigned to {assigned_team}",
        rollback_possible=True,
        rollback_steps={'handler': 'rollback_assign_to_team'},
        before_state=before_state,
        after_state=after_state,
    )
    
    # Create interaction
    TicketInteraction.objects.create(
        ticket=ticket,
        user=ticket.user,
        interaction_type="agent_response",
        content=f"👥 Assigned to {assigned_team}"
    )
    
    logger.info(f"Assigned ticket {ticket.ticket_id} to {assigned_team}")
    return True

def handle_schedule_followup(ticket, params):
    """Schedule a follow-up check."""
    # Schedule another task to check on this ticket later
    followup_time = params.get("followup_time")
    if followup_time:
        check_ticket_followup.apply_async(
            args=[ticket.ticket_id, params],
            eta=followup_time
        )
    
    # Send solution to user but don't auto-resolve
    from integrations.views import send_solution_with_followup
    send_solution_with_followup(str(ticket.user.id), ticket.ticket_id, params)
    
    logger.info(f"Scheduled follow-up for ticket {ticket.ticket_id}")
    return True

def handle_create_kb_article(ticket, params):
    """Create knowledge base article from resolved ticket."""
    ticket.sync_to_knowledge_base()
    logger.info(f"Created KB article from ticket {ticket.ticket_id}")
    return True

@app.task
def check_ticket_followup(ticket_id, original_params):
    """Follow-up task to check if solution worked."""
    try:
        ticket = Ticket.objects.get(ticket_id=ticket_id)
        
        # If still not resolved, escalate
        if ticket.status not in ["resolved", "closed"]:
            logger.info(f"Follow-up: ticket {ticket_id} not resolved, escalating")
            handle_escalate(ticket, {
                "escalation_reason": "Solution did not resolve issue within expected timeframe",
                "priority": "high"
            })
        else:
            logger.info(f"Follow-up: ticket {ticket_id} successfully resolved")
            
    except Exception as e:
        logger.error(f"Error in follow-up check for ticket {ticket_id}: {str(e)}")


@app.task
def schedule_resolution_followup(ticket_id):
    """
    Send follow-up message 24 hours after auto-resolve to verify success.
    This is critical for validating autonomous resolutions actually worked.
    """
    try:
        ticket = Ticket.objects.get(ticket_id=ticket_id)
        
        # Get or create resolution tracking
        resolution, created = TicketResolution.objects.get_or_create(
            ticket=ticket,
            defaults={
                'autonomous_action': ticket.agent_response.get('recommended_action', 'unknown') 
                if isinstance(ticket.agent_response, dict) else 'unknown'
            }
        )
        
        if resolution.followup_sent_at:
            logger.info(f"Follow-up already sent for ticket {ticket_id}")
            return
        
        # Mark follow-up as sent
        resolution.followup_sent_at = timezone.now()
        resolution.save()
        
        # Send Slack message with interactive buttons (if Slack integration available)
        # For now, log it - actual Slack implementation would go here
        logger.info(f"Would send follow-up message for ticket {ticket_id}")
        
        # TODO: Implement actual Slack interactive message
        # from integrations.views import send_slack_feedback_request
        # send_slack_feedback_request(ticket, resolution)
        
    except Ticket.DoesNotExist:
        logger.error(f"Ticket {ticket_id} not found for follow-up")
    except Exception as e:
        logger.error(f"Error sending follow-up for ticket {ticket_id}: {str(e)}")


@app.task(bind=True)
def batch_process_tickets(self, batch_id, ticket_ids, action, force=False):
    """
    Process multiple tickets in batch.
    
    Args:
        batch_id: Unique identifier for this batch
        ticket_ids: List of ticket IDs to process
        action: Action to perform (process, accept, reject)
        force: Force re-processing
    """
    from django.core.cache import cache
    
    logger.info(f"Batch {batch_id}: Processing {len(ticket_ids)} tickets with action '{action}'")
    
    # Initialize batch status
    batch_data = {
        'batch_id': batch_id,
        'total': len(ticket_ids),
        'completed': 0,
        'failed': 0,
        'in_progress': len(ticket_ids),
        'results': []
    }
    cache.set(f'batch_{batch_id}', batch_data, timeout=3600)  # 1 hour
    
    # Process each ticket
    for ticket_id in ticket_ids:
        try:
            logger.info(f"Batch {batch_id}: Processing ticket {ticket_id}")
            
            if action == 'process':
                # Process with agent
                process_ticket_with_agent.delay(ticket_id, force=force)
                result_status = 'completed'
                success = True
                
            elif action == 'accept':
                # Accept agent recommendation (auto-resolve)
                ticket = Ticket.objects.get(ticket_id=ticket_id)
                if ticket.agent_response:
                    recommended_action = ticket.agent_response.get('recommended_action')
                    if recommended_action:
                        # Execute the recommendation
                        agent = AutonomousAgent(ticket)
                        action_enum = AgentAction(recommended_action)
                        params = agent._prepare_action_params(action_enum)
                        execute_autonomous_action(ticket_id, action_enum.value, params)
                        result_status = 'completed'
                        success = True
                    else:
                        result_status = 'failed'
                        success = False
                        error_msg = 'No recommendation available'
                else:
                    result_status = 'failed'
                    success = False
                    error_msg = 'Ticket not processed by agent'
                    
            elif action == 'reject':
                # Reject agent recommendation
                ticket = Ticket.objects.get(ticket_id=ticket_id)
                ticket.agent_response = None
                ticket.agent_processed = False
                ticket.save()
                result_status = 'completed'
                success = True
            
            # Update batch status
            batch_data = cache.get(f'batch_{batch_id}')
            batch_data['completed'] += 1
            batch_data['in_progress'] -= 1
            batch_data['results'].append({
                'ticket_id': ticket_id,
                'status': result_status,
                'success': success
            })
            cache.set(f'batch_{batch_id}', batch_data, timeout=3600)
            
            logger.info(f"Batch {batch_id}: Ticket {ticket_id} {result_status}")
            
        except Exception as e:
            logger.error(f"Batch {batch_id}: Failed to process ticket {ticket_id}: {str(e)}")
            
            # Update batch status with failure
            batch_data = cache.get(f'batch_{batch_id}')
            batch_data['failed'] += 1
            batch_data['in_progress'] -= 1
            batch_data['results'].append({
                'ticket_id': ticket_id,
                'status': 'failed',
                'success': False,
                'error': str(e)
            })
            cache.set(f'batch_{batch_id}', batch_data, timeout=3600)
    
    logger.info(f"Batch {batch_id}: Completed. Success: {batch_data['completed']}, Failed: {batch_data['failed']}")
    return batch_data
