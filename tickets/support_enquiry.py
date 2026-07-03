"""
Create escalated support tickets from billing / account enquiries.
"""
from __future__ import annotations

import logging

from django.utils import timezone

from base.models import SupportContactSubmission, User
from tickets.escalation_copy import (
    REQUEST_REASON_LABEL,
    build_escalation_message,
    compute_sla_due_at,
    derive_escalation_priority,
)
from tickets.handoff import build_handoff_packet
from tickets.models import Ticket, TicketInteraction
from tickets.notifications import run_full_escalation_notifications
from tickets.outcome_helpers import apply_escalated_timestamp
from tickets.scoping import active_team_id_for_user

logger = logging.getLogger(__name__)


def create_billing_support_ticket(
    user: User,
    *,
    subject: str,
    message: str,
    page_context: str,
    submission: SupportContactSubmission,
) -> Ticket:
    """
    Turn a billing support form submission into an escalated ticket linked to the submission.
    Skips AI auto-processing (human queue item).
    """
    from base.models import Team

    team = None
    tid = active_team_id_for_user(user)
    if tid:
        team = Team.objects.filter(pk=tid).first()

    subj = (subject or "Billing / account help").strip()
    max_issue = Ticket._meta.get_field("issue_type").max_length
    issue_type = subj[:max_issue] if subj else "Billing / account help"
    body = (message or "").strip()
    desc = f"Support enquiry from {page_context or 'billing'}:\n\n{body}"

    ticket = Ticket.objects.create(
        user=user,
        team=team,
        issue_type=issue_type,
        description=desc,
        category="billing_account",
        status="escalated",
        awaiting_response_from="support",
        tags=["billing_support"],
        agent_processed=True,
    )
    apply_escalated_timestamp(ticket)
    priority = derive_escalation_priority({"request_reason_key": "billing_account"})
    ticket.escalation_priority = priority
    ticket.sla_due_at = compute_sla_due_at(ticket.escalated_at, priority)
    ticket.last_message_at = timezone.now()
    ticket.last_message_by = user
    ticket.save(
        update_fields=[
            "escalation_priority",
            "sla_due_at",
            "last_message_at",
            "last_message_by",
            "updated_at",
        ]
    )

    TicketInteraction.objects.create(
        ticket=ticket,
        user=user,
        interaction_type="user_message",
        content=f"Billing support request:\n{body[:2000]}",
    )

    reason_text = REQUEST_REASON_LABEL.get("billing_account", "Billing or account issue")
    msg = build_escalation_message(ticket, priority, reason_text)
    packet = build_handoff_packet(ticket, user, body[:2000])
    params = {
        "reason": reason_text,
        "escalation_reason": msg["reason"],
        "priority": msg["priority"],
        "suggested_team": msg["suggested_team"],
        "eta_text": msg["eta_text"],
        "request_reason": reason_text,
        "user_note": body[:500],
        "handoff_text": packet["handoff_text"],
        "handoff_summary": packet["handoff_summary"],
    }
    run_full_escalation_notifications(
        ticket,
        previous_status="new",
        escalation_msg=msg,
        params=params,
        acting_user=user,
    )

    submission.ticket = ticket
    submission.status = SupportContactSubmission.Status.OPEN
    submission.save(update_fields=["ticket", "status"])

    logger.info(
        "Billing support enquiry linked: submission=%s ticket=%s user=%s",
        submission.id,
        ticket.ticket_id,
        user.id,
    )
    return ticket
