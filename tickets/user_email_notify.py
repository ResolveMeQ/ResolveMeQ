"""
User-facing ticket emails (assignment, status changes).
Respects UserPreferences: email_notifications + ticket_updates.
"""
from __future__ import annotations

import logging
from typing import Iterable, Optional

from django.conf import settings

from base.tasks import dispatch_send_email_with_template
from base.user_email_prefs import user_wants_ticket_update_emails

logger = logging.getLogger(__name__)


def _frontend() -> str:
    return getattr(settings, "FRONTEND_URL", "http://localhost:5173").rstrip("/")


def _ticket_url(ticket_id: int) -> str:
    return f"{_frontend()}/tickets?highlight={ticket_id}"


def _app_name() -> str:
    return getattr(settings, "APP_NAME", "ResolveMeQ")


def _recipient_name(user) -> str:
    return (user.get_full_name() or "").strip() or user.email or user.username or "there"


def _send_to_users(
    users: Iterable,
    *,
    subject: str,
    template: str,
    context: dict,
) -> None:
    for u in users:
        if u is None or not getattr(u, "email", None):
            continue
        if not user_wants_ticket_update_emails(u):
            continue
        ctx = {**context, "recipient_name": _recipient_name(u)}
        data = {"subject": subject}
        try:
            dispatch_send_email_with_template(data, template, ctx, [u.email])
        except Exception as exc:
            logger.warning("Ticket email failed for %s: %s", u.email, exc)


def dispatch_ticket_status_emails(ticket, old_status: str, new_status: str) -> None:
    """Email requester and assignee when status changes (if they opted in)."""
    if old_status == new_status:
        return
    recipients = [ticket.user]
    if ticket.assigned_to_id and ticket.assigned_to_id != ticket.user_id:
        recipients.append(ticket.assigned_to)

    subject = f"[{_app_name()}] Ticket #{ticket.ticket_id} is now {new_status.replace('_', ' ')}"
    context = {
        "app_name": _app_name(),
        "ticket_id": ticket.ticket_id,
        "issue_type": ticket.issue_type or "Support ticket",
        "category": ticket.category or "—",
        "old_status": old_status.replace("_", " "),
        "new_status": new_status.replace("_", " "),
        "view_url": _ticket_url(ticket.ticket_id),
    }
    _send_to_users(recipients, subject=subject, template="ticket_status_update.html", context=context)


def dispatch_ticket_assigned_email(ticket, assignee, assigned_by: Optional[object] = None) -> None:
    """Email the new assignee when a ticket is assigned to them."""
    if assignee is None or not getattr(assignee, "email", None):
        return
    assigner = assigned_by
    assigner_name = ""
    if assigner is not None:
        assigner_name = (assigner.get_full_name() or "").strip() or getattr(assigner, "email", "") or ""

    subject = f"[{_app_name()}] Ticket #{ticket.ticket_id} assigned to you"
    context = {
        "app_name": _app_name(),
        "ticket_id": ticket.ticket_id,
        "issue_type": ticket.issue_type or "Support ticket",
        "category": ticket.category or "—",
        "assigner_name": assigner_name or "A teammate",
        "requester_email": getattr(ticket.user, "email", "") or "",
        "view_url": _ticket_url(ticket.ticket_id),
    }
    _send_to_users([assignee], subject=subject, template="ticket_assigned.html", context=context)


def dispatch_ticket_comment_email(ticket, recipients: Iterable, *, commenter, comment_text: str) -> None:
    """Email participants when a new support-thread comment is posted."""
    short = (comment_text or "").strip()
    if len(short) > 280:
        short = short[:277].rsplit(" ", 1)[0] + "..."
    commenter_name = _recipient_name(commenter) if commenter is not None else "A teammate"
    subject = f"[{_app_name()}] New reply on Ticket #{ticket.ticket_id}"
    context = {
        "app_name": _app_name(),
        "ticket_id": ticket.ticket_id,
        "issue_type": ticket.issue_type or "Support ticket",
        "category": ticket.category or "—",
        "commenter_name": commenter_name,
        "comment_text": short,
        "view_url": _ticket_url(ticket.ticket_id),
    }
    _send_to_users(
        recipients,
        subject=subject,
        template="ticket_comment_update.html",
        context=context,
    )
