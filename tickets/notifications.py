"""
Ticket notification helpers.
Shared between views and Celery tasks to avoid circular imports.
"""
import logging
from django.conf import settings

from base.models import User, InAppNotification

logger = logging.getLogger(__name__)


def _send_escalation_email(staff_user, ticket, params):
    """Send escalation email to a staff member. Runs in Celery for async delivery."""
    email = getattr(staff_user, "email", None)
    if not email or not email.strip():
        return
    frontend_url = getattr(settings, "FRONTEND_URL", "https://app.resolvemeq.net")
    view_url = f"{frontend_url}/tickets?highlight={ticket.ticket_id}"
    requester = getattr(ticket.user, "email", None) or getattr(ticket.user, "username", None) or "User"
    staff_name = getattr(staff_user, "first_name", None) or getattr(staff_user, "username", None) or "Support"
    if hasattr(staff_user, "get_full_name") and staff_user.get_full_name():
        staff_name = staff_user.get_full_name()
    context = {
        "staff_name": staff_name,
        "ticket_id": ticket.ticket_id,
        "requester_email": requester,
        "issue_type": ticket.issue_type or "Support needed",
        "category": ticket.category or "—",
        "description": (ticket.description or "")[:500],
        "conversation_summary": params.get("conversation_summary", "")[:400],
        "view_url": view_url,
        "app_name": "ResolveMeQ",
    }
    data = {"subject": f"[Escalation] Ticket #{ticket.ticket_id}: {ticket.issue_type or 'Support needed'}"}
    try:
        from base.tasks import send_email_with_template
        send_email_with_template.delay(data, "escalation_notification.html", context, [email])
    except Exception as e:
        logger.warning("Failed to queue escalation email for %s: %s", email, e)


def notify_support_escalation(ticket, params):
    """
    Notify support staff when a ticket is escalated.
    Creates in-app notifications, sends emails, and optionally posts to Slack.
    """
    try:
        for user in User.objects.filter(is_staff=True):
            if user.id == ticket.user_id:
                continue
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
            if getattr(settings, "EMAIL_HOST_USER", None):
                _send_escalation_email(user, ticket, params)
        try:
            from integrations.views import notify_support_escalation_slack
            notify_support_escalation_slack(ticket, params)
        except Exception as e:
            logger.warning("Slack support escalation notification failed: %s", e)
    except Exception as e:
        logger.warning("Failed to notify support of escalation: %s", e)
