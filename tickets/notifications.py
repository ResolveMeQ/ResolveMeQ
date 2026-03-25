"""
Ticket notification helpers.
Shared between views and Celery tasks to avoid circular imports.
"""
import logging
from django.conf import settings

from base.models import User, InAppNotification

logger = logging.getLogger(__name__)


def _escalation_recipient_emails():
    """
    Email addresses to notify on escalation (operators — not tied to is_staff / is_superuser).
    Set Django ADMINS and/or SUPPORT_ESCALATION_EMAILS in settings.
    """
    emails = []
    for _, email in getattr(settings, "ADMINS", []) or []:
        if email and str(email).strip():
            emails.append(str(email).strip())
    extra = getattr(settings, "SUPPORT_ESCALATION_EMAILS", None)
    if isinstance(extra, str) and extra.strip():
        emails.append(extra.strip())
    elif isinstance(extra, (list, tuple)):
        for e in extra:
            if e and str(e).strip():
                emails.append(str(e).strip())
    seen = set()
    out = []
    for e in emails:
        key = e.lower()
        if key not in seen:
            seen.add(key)
            out.append(e)
    return out


def _send_escalation_email(to_email, ticket, params):
    """Queue escalation email to an address. Runs in Celery for async delivery."""
    email = str(to_email).strip()
    if not email:
        return
    frontend_url = getattr(settings, "FRONTEND_URL", "https://app.resolvemeq.net")
    view_url = f"{frontend_url}/tickets?highlight={ticket.ticket_id}"
    requester = getattr(ticket.user, "email", None) or getattr(ticket.user, "username", None) or "User"
    context = {
        "staff_name": "Support",
        "ticket_id": ticket.ticket_id,
        "requester_email": requester,
        "issue_type": ticket.issue_type or "Support needed",
        "category": ticket.category or "—",
        "description": (ticket.description or "")[:500],
        "conversation_summary": params.get("conversation_summary", "")[:400],
        "handoff_text": (params.get("handoff_text") or "")[:4000],
        "handoff_summary": (params.get("handoff_summary") or "")[:600],
        "view_url": view_url,
        "app_name": "ResolveMeQ",
    }
    data = {"subject": f"[Escalation] Ticket #{ticket.ticket_id}: {ticket.issue_type or 'Support needed'}"}
    try:
        from base.tasks import dispatch_send_email_with_template
        dispatch_send_email_with_template(data, "escalation_notification.html", context, [email])
    except Exception as e:
        logger.warning("Failed to queue escalation email for %s: %s", email, e)


def notify_support_escalation(ticket, params):
    """
    Notify configured operators when a ticket is escalated (see ADMINS / SUPPORT_ESCALATION_EMAILS).
    In-app notifications only for User accounts whose email matches those addresses.
    """
    try:
        emails = _escalation_recipient_emails()
        if not emails:
            logger.info(
                "Escalation ticket #%s: configure ADMINS or SUPPORT_ESCALATION_EMAILS for operator alerts.",
                ticket.ticket_id,
            )
        else:
            if getattr(settings, "EMAIL_HOST_USER", None):
                for email in emails:
                    _send_escalation_email(email, ticket, params)
            for user in User.objects.filter(email__in=emails, is_active=True).exclude(id=ticket.user_id):
                InAppNotification.objects.create(
                    user=user,
                    type=InAppNotification.Type.WARNING,
                    title="Ticket escalated",
                    message=(
                        f"Ticket #{ticket.ticket_id} from "
                        f"{getattr(ticket.user, 'email', ticket.user.username or 'User')}: "
                        f"{ticket.issue_type or 'Support needed'}"
                    ),
                    link=f"/tickets?highlight={ticket.ticket_id}",
                )
        try:
            from integrations.views import notify_support_escalation_slack
            notify_support_escalation_slack(ticket, params)
        except Exception as e:
            logger.warning("Slack support escalation notification failed: %s", e)
    except Exception as e:
        logger.warning("Failed to notify support of escalation: %s", e)
