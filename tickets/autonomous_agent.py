from enum import Enum
from typing import Dict, Any, Tuple
from datetime import datetime, timedelta
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

class AgentAction(Enum):
    AUTO_RESOLVE = "auto_resolve"
    ESCALATE = "escalate"
    REQUEST_CLARIFICATION = "request_clarification"
    ASSIGN_TO_TEAM = "assign_to_team"
    SCHEDULE_FOLLOWUP = "schedule_followup"
    CREATE_KB_ARTICLE = "create_kb_article"

class AutonomousAgent:
    """
    Autonomous agent that makes decisions and takes actions based on AI analysis.
    """
    
    # Confidence thresholds for different actions
    HIGH_CONFIDENCE_THRESHOLD = 0.8
    MEDIUM_CONFIDENCE_THRESHOLD = 0.6
    LOW_CONFIDENCE_THRESHOLD = 0.3
    
    def __init__(self, ticket):
        self.ticket = ticket
        self.agent_response = ticket.agent_response or {}
        
    def get_confidence(self) -> float:
        """Extract confidence score from agent response."""
        return self.agent_response.get("confidence", 0.0)
    
    def get_recommended_action(self) -> str:
        """Extract recommended action from agent response."""
        return self.agent_response.get("recommended_action", "request_clarification")
    
    def get_success_probability(self) -> float:
        """Extract solution success probability."""
        solution = self.agent_response.get("solution", {})
        return solution.get("success_probability", 0.0)
    
    def decide_autonomous_action(self) -> Tuple[AgentAction, Dict[str, Any]]:
        """
        Main decision engine that determines what action to take autonomously.
        Returns: (action, action_params)
        """
        confidence = self.get_confidence()
        recommended_action = self.get_recommended_action()
        success_prob = self.get_success_probability()
        
        logger.info(f"Agent decision for ticket {self.ticket.ticket_id}: "
                   f"confidence={confidence}, recommended={recommended_action}, success_prob={success_prob}")
        
        # High confidence - take autonomous action
        if confidence >= self.HIGH_CONFIDENCE_THRESHOLD:
            if recommended_action == "auto_resolve" and success_prob >= 0.8:
                return AgentAction.AUTO_RESOLVE, self._prepare_auto_resolve_params()
            elif recommended_action == "escalate":
                return AgentAction.ESCALATE, self._prepare_escalate_params()
            elif recommended_action == "assign_to_team":
                return AgentAction.ASSIGN_TO_TEAM, self._prepare_assign_params()
            elif recommended_action == "request_clarification":
                return AgentAction.REQUEST_CLARIFICATION, self._prepare_clarification_params()
            else:
                # Default for high confidence: schedule followup
                return AgentAction.SCHEDULE_FOLLOWUP, self._prepare_followup_params()
        
        # Medium confidence - take cautious action with user notification
        elif confidence >= self.MEDIUM_CONFIDENCE_THRESHOLD:
            if recommended_action == "auto_resolve":
                return AgentAction.SCHEDULE_FOLLOWUP, self._prepare_followup_params()
            else:
                return AgentAction.REQUEST_CLARIFICATION, self._prepare_clarification_params()
        
        # Low confidence - escalate or request more info
        else:
            if self._is_critical_issue():
                return AgentAction.ESCALATE, self._prepare_escalate_params()
            else:
                return AgentAction.REQUEST_CLARIFICATION, self._prepare_clarification_params()
    
    def _is_critical_issue(self) -> bool:
        """Determine if this is a critical issue that needs immediate attention."""
        analysis = self.agent_response.get("analysis", {})
        severity = analysis.get("severity", "").lower()
        category = analysis.get("category", "").lower()
        
        return (severity in ["critical", "high"] or 
                category in ["security", "outage", "data_loss"])
    
    def _prepare_auto_resolve_params(self) -> Dict[str, Any]:
        """Prepare parameters for auto-resolution."""
        solution = self.agent_response.get("solution", {})
        return {
            "resolution_steps": solution.get("steps", []),
            "estimated_time": solution.get("estimated_time", "Unknown"),
            "reasoning": self.agent_response.get("reasoning", ""),
            "auto_resolved": True
        }
    
    def _prepare_escalate_params(self) -> Dict[str, Any]:
        """Prepare parameters for escalation."""
        analysis = self.agent_response.get("analysis", {})
        return {
            "escalation_reason": self.agent_response.get("reasoning", "Complex issue requiring human attention"),
            "severity": analysis.get("severity", "medium"),
            "suggested_team": analysis.get("suggested_team", "IT Support"),
            "priority": "high" if self._is_critical_issue() else "medium"
        }
    
    def _prepare_assign_params(self) -> Dict[str, Any]:
        """Prepare parameters for team assignment."""
        analysis = self.agent_response.get("analysis", {})
        return {
            "assigned_team": analysis.get("suggested_team", "IT Support"),
            "reasoning": self.agent_response.get("reasoning", ""),
            "priority": analysis.get("severity", "medium")
        }
    
    def _prepare_followup_params(self) -> Dict[str, Any]:
        """Prepare parameters for scheduled follow-up."""
        solution = self.agent_response.get("solution", {})
        estimated_time = solution.get("estimated_time", "30 minutes")
        
        # Parse estimated time and schedule follow-up
        followup_delay = self._parse_time_to_minutes(estimated_time) + 15  # Add 15 min buffer
        
        return {
            "solution_steps": solution.get("steps", []),
            "followup_time": timezone.now() + timedelta(minutes=followup_delay),
            "confidence_level": self.get_confidence(),
            "auto_check": True
        }
    
    def _prepare_clarification_params(self) -> Dict[str, Any]:
        """Prepare parameters for requesting clarification."""
        analysis = self.agent_response.get("analysis", {})
        return {
            "questions": analysis.get("clarification_questions", [
                "Can you provide more details about the issue?",
                "When did this problem first occur?",
                "What steps have you already tried?"
            ]),
            "reason": "Need additional information to provide accurate solution",
            "confidence": self.get_confidence()
        }
    
    def _parse_time_to_minutes(self, time_str: str) -> int:
        """Parse time strings like '5 minutes', '1 hour' to minutes."""
        time_str = time_str.lower()
        if "minute" in time_str:
            return int(''.join(filter(str.isdigit, time_str)) or "30")
        elif "hour" in time_str:
            return int(''.join(filter(str.isdigit, time_str)) or "1") * 60
        elif "day" in time_str:
            return int(''.join(filter(str.isdigit, time_str)) or "1") * 24 * 60
        else:
            return 30  # Default 30 minutes
