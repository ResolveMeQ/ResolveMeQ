"""
Monitoring and metrics tracking for autonomous agent performance.
Integrates with Sentry for real-time error tracking and performance monitoring.
"""
from sentry_sdk import capture_message, capture_exception, set_tag, set_context
import logging

logger = logging.getLogger(__name__)


class AgentMetrics:
    """Track autonomous agent performance metrics and send to Sentry"""
    
    @staticmethod
    def track_autonomous_action(action_type, ticket_id, confidence, success):
        """
        Log autonomous action with context to Sentry.
        
        Args:
            action_type: Type of autonomous action (AUTO_RESOLVE, ESCALATE, etc.)
            ticket_id: ID of the ticket being processed
            confidence: AI confidence score (0.0-1.0)
            success: Whether the action succeeded
        """
        try:
            set_tag("action_type", action_type)
            set_tag("success", success)
            set_tag("confidence_level", "high" if confidence >= 0.8 else "medium" if confidence >= 0.6 else "low")
            
            set_context("agent_action", {
                "ticket_id": ticket_id,
                "confidence": confidence,
                "action_type": action_type,
                "success": success,
            })
            
            if not success:
                capture_message(
                    f"Autonomous action failed: {action_type}",
                    level="warning"
                )
            
            logger.info(f"Tracked autonomous action: {action_type} for ticket {ticket_id} (confidence: {confidence}, success: {success})")
            
        except Exception as e:
            logger.error(f"Error tracking autonomous action: {str(e)}")
    
    @staticmethod
    def track_agent_error(error, ticket_id, context=None):
        """
        Capture agent processing errors and send to Sentry.
        
        Args:
            error: The exception that occurred
            ticket_id: ID of the ticket being processed
            context: Additional context dictionary
        """
        try:
            set_tag("component", "autonomous_agent")
            set_tag("ticket_id", str(ticket_id))
            
            if context:
                set_context("error_context", context)
            
            capture_exception(error)
            logger.error(f"Agent error for ticket {ticket_id}: {str(error)}")
            
        except Exception as e:
            logger.error(f"Error in error tracking: {str(e)}")
    
    @staticmethod
    def track_confidence_score(ticket_id, confidence, category):
        """
        Track confidence scores for analytics.
        
        Args:
            ticket_id: ID of the ticket
            confidence: AI confidence score
            category: Ticket category
        """
        try:
            set_tag("ticket_category", category)
            set_context("confidence_tracking", {
                "ticket_id": ticket_id,
                "confidence": confidence,
                "category": category,
            })
            
            # Alert on consistently low confidence
            if confidence < 0.3:
                capture_message(
                    f"Very low confidence score ({confidence}) for ticket {ticket_id}",
                    level="info"
                )
                
        except Exception as e:
            logger.error(f"Error tracking confidence score: {str(e)}")
