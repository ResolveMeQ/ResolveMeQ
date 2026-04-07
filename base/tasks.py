from __future__ import annotations

import logging
import os
import re
import sys
from datetime import timedelta
from typing import Optional

from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)


def _email_dispatch_uses_celery() -> bool:
    """
    Queue outbound mail via Celery when workers are expected.

    If EMAIL_USE_CELERY is unset, default to synchronous delivery while
    ``runserver`` is used so verification/password emails are not dropped
    when no worker is running (tasks would sit in Redis).
    """
    explicit = os.getenv("EMAIL_USE_CELERY", "").strip().lower()
    if explicit in ("0", "false", "no"):
        return False
    if explicit in ("1", "true", "yes"):
        return True
    return "runserver" not in sys.argv


def email_dispatch_uses_celery() -> bool:
    """Public alias for health checks and ops tooling."""
    return _email_dispatch_uses_celery()


def _transactional_from_email() -> Optional[str]:
    """From header: prefer DEFAULT_FROM_EMAIL (must match SPF/DKIM for your domain)."""
    return getattr(settings, "DEFAULT_FROM_EMAIL", None) or getattr(settings, "EMAIL_HOST_USER", None)


def _html_to_plain(html: str) -> str:
    """Plain-text part for multipart/alternative (improves deliverability vs HTML-only)."""
    text = strip_tags(html)
    text = re.sub(r"[\t\r\f\v]", " ", text)
    text = re.sub(r" +", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    text = text.strip()
    return text or "This message requires an HTML-capable email client."


def dispatch_send_email_with_template(
    data: dict, template_name: str, context: dict, recipient: list
) -> None:
    if _email_dispatch_uses_celery():
        try:
            send_email_with_template.delay(data, template_name, context, recipient)
        except Exception as exc:
            # Broker unreachable or queue failure — still try SMTP from this process
            logger.warning(
                "Celery enqueue failed for %s → %s; sending synchronously. Error: %s",
                template_name,
                recipient,
                exc,
                exc_info=True,
            )
            send_email_with_template(data, template_name, context, recipient)
    else:
        logger.info("Sending email synchronously (no Celery queue for this process)")
        send_email_with_template(data, template_name, context, recipient)


@shared_task(name="base.health_ping")
def health_ping() -> dict:
    """
    Lightweight task for monitoring: verifies a worker can dequeue and run a task.
    Used by GET /api/monitoring/health/services/ (admin) and /health/complete/ (token).
    """
    from django.utils import timezone

    return {"ok": True, "worker_timestamp": timezone.now().isoformat()}


@shared_task
def send_email_with_template(data: dict, template_name: str, context: dict, recipient: list):
    template_name = f"emails/{template_name}"
    html_body = render_to_string(template_name, context)
    plain_body = _html_to_plain(html_body)
    from_email = _transactional_from_email()
    if not from_email:
        msg = "Set DEFAULT_FROM_EMAIL or EMAIL_HOST_USER in settings / .env"
        logger.error("Email not sent: %s", msg)
        raise ValueError(msg)

    headers = {}
    support = getattr(settings, "SUPPORT_EMAIL", "") or ""
    if support:
        headers["Reply-To"] = support

    email = EmailMultiAlternatives(
        subject=data["subject"],
        body=plain_body,
        from_email=from_email,
        to=recipient,
        headers=headers,
    )
    email.attach_alternative(html_body, "text/html")
    try:
        email.send()
        logger.info("Email sent to %s", recipient)
    except Exception as e:
        logger.error("Email sending failed: %s", str(e), exc_info=True)
        raise


@shared_task
def send_daily_digest_emails() -> None:
    """
    Daily summary for users who enabled Settings → Daily digest (and email notifications).
    Scheduled via Celery Beat (see CELERY_BEAT_SCHEDULE).
    """
    from django.contrib.auth import get_user_model
    from django.db.models import Q
    from django.utils import timezone

    from base.models import TeamInvitation, UserPreferences
    from base.user_email_prefs import user_wants_digest_emails
    from tickets.models import Ticket

    User = get_user_model()
    if not _transactional_from_email():
        logger.warning("Daily digest skipped: set DEFAULT_FROM_EMAIL or EMAIL_HOST_USER")
        return

    now = timezone.now()
    since = now - timedelta(hours=24)
    frontend = getattr(settings, "FRONTEND_URL", "http://localhost:5173").rstrip("/")
    app_name = getattr(settings, "APP_NAME", "ResolveMeQ")

    prefs = (
        UserPreferences.objects.filter(email_notifications=True, daily_digest=True)
        .select_related("user")
        .iterator(chunk_size=100)
    )

    digest_enqueued = 0
    for pref in prefs:
        user = pref.user
        if not user.is_active or not user.email:
            continue
        if not user_wants_digest_emails(user):
            continue

        scope = Q(user=user) | Q(assigned_to=user)
        open_ticket_count = Ticket.objects.filter(scope).exclude(status="resolved").count()
        recent_updates_count = Ticket.objects.filter(scope, updated_at__gte=since).count()
        recent_qs = (
            Ticket.objects.filter(scope, updated_at__gte=since)
            .order_by("-updated_at")
            .values("ticket_id", "issue_type", "status")[:8]
        )
        recent_tickets = [
            {
                "id": row["ticket_id"],
                "title": (row["issue_type"] or "Ticket")[:120],
                "status": (row["status"] or "").replace("_", " "),
            }
            for row in recent_qs
        ]
        pending_invites_count = TeamInvitation.objects.filter(
            email__iexact=user.email,
            status=TeamInvitation.Status.PENDING,
        ).count()

        recipient_name = (user.get_full_name() or "").strip() or user.email
        context = {
            "app_name": app_name,
            "digest_date": now.strftime("%Y-%m-%d %H:%M UTC"),
            "recipient_name": recipient_name,
            "open_ticket_count": open_ticket_count,
            "recent_updates_count": recent_updates_count,
            "recent_tickets": recent_tickets,
            "pending_invites_count": pending_invites_count,
            "tickets_url": f"{frontend}/tickets",
            "teams_url": f"{frontend}/teams",
        }
        data = {"subject": f"{app_name} daily summary — {now.strftime('%Y-%m-%d')}"}
        try:
            dispatch_send_email_with_template(
                data, "daily_digest.html", context, [user.email]
            )
            digest_enqueued += 1
        except Exception as exc:
            logger.warning("Daily digest failed for %s: %s", user.email, exc)

    logger.info("Daily digest finished: enqueued %s digest email(s)", digest_enqueued)
