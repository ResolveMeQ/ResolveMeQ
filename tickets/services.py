"""
Shared ticket operations used by the REST API and channel integrations (e.g. Slack).
"""

import logging

from base.models import InAppNotification, User
from tickets.models import Ticket, TicketInteraction

logger = logging.getLogger(__name__)

VALID_URGENCY = frozenset({"low", "medium", "high"})


def compose_issue_type(subject: str, urgency: str | None = None) -> str:
    """
    Single format for `Ticket.issue_type` when urgency is set: "Subject (urgency)".
    Truncates to the model's max_length. Omit or pass invalid urgency to store subject only.
    """
    max_len = Ticket._meta.get_field("issue_type").max_length
    base = (subject or "").strip()
    if not base:
        return ""
    u = (urgency or "").strip().lower()
    if u in VALID_URGENCY:
        out = f"{base} ({u})"
    else:
        out = base
    return out[:max_len] if len(out) > max_len else out


def create_ticket_with_reporter(
    user: User,
    team=None,
    *,
    issue_type: str,
    description: str | None = "",
    category: str = "other",
    screenshot: str | None = None,
    status: str = "new",
    tags=None,
    assigned_to=None,
) -> Ticket:
    """
    Create a ticket plus the initial interaction and in-app notification.
    Agent processing is queued by tickets.signals.ticket_created (post_save).
    """
    tags = tags if tags is not None else []
    ticket = Ticket.objects.create(
        user=user,
        team=team,
        issue_type=issue_type,
        status=status,
        description=description or "",
        screenshot=screenshot or None,
        category=category,
        tags=tags,
        assigned_to=assigned_to,
    )
    TicketInteraction.objects.create(
        ticket=ticket,
        user=user,
        interaction_type="user_message",
        content=f"Ticket created: {ticket.description}",
    )
    try:
        InAppNotification.objects.create(
            user=user,
            type=InAppNotification.Type.INFO,
            title="Ticket created",
            message=f"Ticket #{ticket.ticket_id} has been created. We'll get back to you soon.",
            link=f"/tickets?highlight={ticket.ticket_id}",
        )
    except Exception as exc:
        logger.warning("Failed to create ticket-created notification: %s", exc)
    return ticket
