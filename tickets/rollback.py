"""
Rollback mechanisms for autonomous actions.
Enables recovery from incorrect agent decisions with full audit trail.
"""
from django.utils import timezone
from .models import Ticket, ActionHistory, TicketInteraction
import logging

logger = logging.getLogger(__name__)


class RollbackManager:
    """Manage rollback of autonomous actions"""
    
    @staticmethod
    def rollback_auto_resolve(ticket, action_history, rollback_by, reason):
        """
        Revert an AUTO_RESOLVE action.
        
        Args:
            ticket: Ticket instance
            action_history: ActionHistory instance to rollback
            rollback_by: User performing the rollback
            reason: Reason for rollback
            
        Returns:
            bool: True if rollback succeeded, False otherwise
        """
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
                content=f"🔄 Auto-resolution was rolled back.\n\nReason: {reason}\n\nTicket reopened for manual review."
            )
            
            # Mark action as rolled back
            action_history.rolled_back = True
            action_history.rolled_back_at = timezone.now()
            action_history.rolled_back_by = rollback_by
            action_history.rollback_reason = reason
            action_history.save()
            
            logger.info(f"Successfully rolled back AUTO_RESOLVE for ticket {ticket.ticket_id}")
            return True
            
        except Exception as e:
            logger.error(f"Rollback failed for ticket {ticket.ticket_id}: {str(e)}")
            return False
    
    @staticmethod
    def rollback_assign_to_team(ticket, action_history, rollback_by, reason):
        """
        Revert a team assignment action.
        
        Args:
            ticket: Ticket instance
            action_history: ActionHistory instance to rollback
            rollback_by: User performing the rollback
            reason: Reason for rollback
            
        Returns:
            bool: True if rollback succeeded, False otherwise
        """
        try:
            from base.models import User
            
            # Restore previous assignment
            if action_history.before_state:
                prev_assignee_id = action_history.before_state.get('assigned_to_id')
                if prev_assignee_id:
                    ticket.assigned_to = User.objects.get(user_id=prev_assignee_id)
                else:
                    ticket.assigned_to = None
            else:
                ticket.assigned_to = None
            
            ticket.save()
            
            # Add interaction explaining rollback
            TicketInteraction.objects.create(
                ticket=ticket,
                user=rollback_by,
                interaction_type='agent_response',
                content=f"🔄 Team assignment was rolled back.\n\nReason: {reason}"
            )
            
            # Mark action as rolled back
            action_history.rolled_back = True
            action_history.rolled_back_at = timezone.now()
            action_history.rolled_back_by = rollback_by
            action_history.rollback_reason = reason
            action_history.save()
            
            logger.info(f"Successfully rolled back team assignment for ticket {ticket.ticket_id}")
            return True
            
        except Exception as e:
            logger.error(f"Team assignment rollback failed for ticket {ticket.ticket_id}: {str(e)}")
            return False
    
    @staticmethod
    def rollback_escalate(ticket, action_history, rollback_by, reason):
        """
        Revert an escalation action.
        
        Args:
            ticket: Ticket instance
            action_history: ActionHistory instance to rollback
            rollback_by: User performing the rollback
            reason: Reason for rollback
            
        Returns:
            bool: True if rollback succeeded, False otherwise
        """
        try:
            # Restore previous state
            if action_history.before_state:
                ticket.status = action_history.before_state.get('status', 'new')
            else:
                ticket.status = 'new'
            
            ticket.save()
            
            # Add interaction
            TicketInteraction.objects.create(
                ticket=ticket,
                user=rollback_by,
                interaction_type='agent_response',
                content=f"🔄 Escalation was rolled back.\n\nReason: {reason}"
            )
            
            # Mark action as rolled back
            action_history.rolled_back = True
            action_history.rolled_back_at = timezone.now()
            action_history.rolled_back_by = rollback_by
            action_history.rollback_reason = reason
            action_history.save()
            
            logger.info(f"Successfully rolled back escalation for ticket {ticket.ticket_id}")
            return True
            
        except Exception as e:
            logger.error(f"Escalation rollback failed for ticket {ticket.ticket_id}: {str(e)}")
            return False
    
    @staticmethod
    def can_rollback(action_type):
        """
        Check if action type supports rollback.
        
        Args:
            action_type: The type of autonomous action
            
        Returns:
            bool: True if rollback is supported for this action type
        """
        ROLLBACK_SUPPORTED = [
            'AUTO_RESOLVE',
            'ASSIGN_TO_TEAM',
            'ESCALATE',
            'SCHEDULE_FOLLOWUP',
        ]
        return action_type in ROLLBACK_SUPPORTED
    
    @staticmethod
    def execute_rollback(action_history, rollback_by, reason):
        """
        Execute rollback based on action type.
        
        Args:
            action_history: ActionHistory instance to rollback
            rollback_by: User performing the rollback
            reason: Reason for rollback
            
        Returns:
            bool: True if rollback succeeded, False otherwise
        """
        action_type = action_history.action_type
        ticket = action_history.ticket
        
        if action_type == 'AUTO_RESOLVE':
            return RollbackManager.rollback_auto_resolve(ticket, action_history, rollback_by, reason)
        elif action_type == 'ASSIGN_TO_TEAM':
            return RollbackManager.rollback_assign_to_team(ticket, action_history, rollback_by, reason)
        elif action_type == 'ESCALATE':
            return RollbackManager.rollback_escalate(ticket, action_history, rollback_by, reason)
        else:
            logger.warning(f"No rollback handler for action type: {action_type}")
            return False
