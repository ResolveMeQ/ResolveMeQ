"""
Single source of truth for escalation priority/SLA/copy.

Before this module existed, the same escalation event was described independently
in 4+ places (Slack DM, in-app notification, two frontend toasts, the chat panel,
the ticket-detail banner) and they drifted -- e.g. the manual "Request human help"
path never actually set the keys the Slack message read, so it always showed a
generic fallback. Every channel should build its text from build_escalation_message()
instead of writing its own string.
"""
from django.utils import timezone

from .sla_settings import escalation_sla_hours

_VALID_PRIORITIES = {"critical", "high", "medium", "low"}
PRIORITY_LADDER = ["low", "medium", "high", "critical"]


def bump_priority_tier(priority):
    """One tier more urgent (low -> medium -> high -> critical). Already-critical
    (or unrecognized) priority is returned unchanged -- there's nowhere higher to go."""
    try:
        idx = PRIORITY_LADDER.index(priority)
    except ValueError:
        return priority
    return PRIORITY_LADDER[min(idx + 1, len(PRIORITY_LADDER) - 1)]

# Manual escalation modal's `reason` dropdown values (Tickets.jsx escalateForm.reason)
# mapped to a priority -- reuses a signal the UI already collects instead of guessing.
REQUEST_REASON_PRIORITY = {
    "urgent_blocked": "high",
    "security_access": "high",
    "billing_account": "medium",
    "talk_to_human": "medium",
    "other": "medium",
}

REQUEST_REASON_LABEL = {
    "urgent_blocked": "Urgent — blocked and needs help now",
    "security_access": "Security or access issue",
    "billing_account": "Billing or account issue",
    "talk_to_human": "Requested to talk to a support specialist",
    "other": "Requested human help",
}


def derive_escalation_priority(params=None):
    """
    Priority precedence: explicit autonomous-path signal (severity/priority from the
    AI's analysis) > manual escalation request_reason_key mapping > 'medium' default.
    """
    params = params or {}
    explicit = (params.get("priority") or "").lower()
    if explicit in _VALID_PRIORITIES:
        return explicit
    severity = (params.get("severity") or "").lower()
    if severity in _VALID_PRIORITIES:
        return severity
    reason_key = params.get("request_reason_key") or ""
    return REQUEST_REASON_PRIORITY.get(reason_key, "medium")


def compute_sla_due_at(escalated_at, priority):
    if not escalated_at:
        return None
    return escalated_at + timezone.timedelta(hours=escalation_sla_hours(priority))


def build_escalation_message(ticket, priority, reason_text=None, suggested_team=None):
    """Returns the dict every channel (Slack, in-app, email, API response) renders from."""
    priority = priority if priority in _VALID_PRIORITIES else "medium"
    eta_hours = escalation_sla_hours(priority)
    eta_text = f"within about {int(eta_hours)} hours" if eta_hours >= 1 else "shortly"
    team = suggested_team or "our support team"
    reason = reason_text or "Requested human help"
    return {
        "priority": priority,
        "reason": reason,
        "suggested_team": team,
        "eta_hours": eta_hours,
        "eta_text": eta_text,
        "title": f"Ticket #{ticket.ticket_id} escalated",
        "body": f"Escalated to {team} ({priority.upper()} priority). Expect a response {eta_text}.",
    }
