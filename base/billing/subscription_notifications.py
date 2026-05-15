"""
Subscription lifecycle emails and in-app notifications (subscribe, renew, expiring, expired).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from django.conf import settings
from django.utils import timezone
from django.utils.formats import date_format

from base.tasks import dispatch_send_email_with_template
from base.user_email_prefs import user_wants_billing_emails

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SubscriptionSnapshot:
    status: str
    plan_id: Optional[Any]
    gateway_subscription_id: str
    current_period_end: Optional[datetime]
    trial_ends_at: Optional[datetime]
    subscription_welcome_notified_at: Optional[datetime]
    subscription_renewed_notified_period_end: Optional[datetime]


def snapshot_subscription(sub) -> SubscriptionSnapshot:
    return SubscriptionSnapshot(
        status=(sub.status or "").strip(),
        plan_id=sub.plan_id,
        gateway_subscription_id=(sub.gateway_subscription_id or "").strip(),
        current_period_end=sub.current_period_end,
        trial_ends_at=sub.trial_ends_at,
        subscription_welcome_notified_at=sub.subscription_welcome_notified_at,
        subscription_renewed_notified_period_end=sub.subscription_renewed_notified_period_end,
    )


def _frontend_billing_url() -> str:
    frontend = getattr(settings, "FRONTEND_URL", "http://localhost:5173").rstrip("/")
    return f"{frontend}/billing"


def _format_dt(dt: Optional[datetime]) -> str:
    if not dt:
        return ""
    try:
        return date_format(timezone.localtime(dt), "DATETIME_FORMAT")
    except Exception:
        return dt.strftime("%Y-%m-%d %H:%M UTC")


def _billing_email_context(user, sub) -> dict:
    app_name = getattr(settings, "APP_NAME", "ResolveMeQ")
    plan = getattr(sub, "plan", None)
    plan_name = getattr(plan, "name", None) or "your plan"
    return {
        "app_name": app_name,
        "recipient_name": (user.get_full_name() or "").strip() or user.email,
        "billing_url": _frontend_billing_url(),
        "frontend_url": getattr(settings, "FRONTEND_URL", "http://localhost:5173").rstrip("/"),
        "support_email": getattr(settings, "SUPPORT_EMAIL", "") or "",
        "plan_name": plan_name,
        "period_end_display": _format_dt(sub.current_period_end),
        "trial_end_display": _format_dt(sub.trial_ends_at),
    }


def _create_in_app(user, *, ntype, title: str, message: str) -> None:
    from base.models import InAppNotification

    try:
        InAppNotification.objects.create(
            user=user,
            type=ntype,
            title=title,
            message=message,
            link="/billing",
        )
    except Exception as exc:
        logger.warning("Billing in-app notify failed for %s: %s", user.id, exc)


def _send_billing_email(user, *, subject: str, template: str, context: dict) -> bool:
    if not user_wants_billing_emails(user):
        return False
    try:
        dispatch_send_email_with_template(
            {"subject": subject},
            template,
            context,
            [user.email],
        )
        return True
    except Exception as exc:
        logger.warning("Billing email failed for %s (%s): %s", user.email, template, exc)
        return False


def notify_subscription_welcome(sub) -> bool:
    """First paid subscription via checkout (Dodo)."""
    user = sub.user
    if not user.is_active or not user.email:
        return False
    if sub.subscription_welcome_notified_at:
        return False
    if not (sub.gateway_subscription_id or "").strip():
        return False
    if sub.status not in (sub.Status.ACTIVE, sub.Status.TRIAL):
        return False
    if not sub.plan_id:
        return False

    ctx = _billing_email_context(user, sub)
    app_name = ctx["app_name"]
    detail = (
        f'Your trial on "{ctx["plan_name"]}" is active.'
        if sub.status == sub.Status.TRIAL
        else f'You are subscribed to "{ctx["plan_name"]}".'
    )
    ctx["welcome_detail"] = detail

    _send_billing_email(
        user,
        subject=f"{app_name}: subscription confirmed",
        template="subscription_welcome.html",
        context=ctx,
    )
    from base.models import InAppNotification

    _create_in_app(
        user,
        ntype=InAppNotification.Type.SUCCESS,
        title="Subscription confirmed",
        message=f'{detail} Open Billing to manage your plan.',
    )

    now = timezone.now()
    sub.subscription_welcome_notified_at = now
    sub.subscription_expired_notified_at = None
    sub.save(
        update_fields=[
            "subscription_welcome_notified_at",
            "subscription_expired_notified_at",
            "updated_at",
        ]
    )
    return True


def notify_subscription_renewed(sub, *, period_end: datetime) -> bool:
    """Billing period extended (renewal or successful payment)."""
    user = sub.user
    if not user.is_active or not user.email:
        return False
    if sub.status != sub.Status.ACTIVE:
        return False
    if not (sub.gateway_subscription_id or "").strip():
        return False
    if not period_end:
        return False
    if sub.subscription_renewed_notified_period_end == period_end:
        return False

    ctx = _billing_email_context(user, sub)
    ctx["renewal_detail"] = (
        f'Your "{ctx["plan_name"]}" subscription has been renewed. '
        f'Next billing date: {ctx["period_end_display"] or _format_dt(period_end)}.'
    )
    app_name = ctx["app_name"]

    _send_billing_email(
        user,
        subject=f"{app_name}: subscription renewed",
        template="subscription_renewed.html",
        context=ctx,
    )
    from base.models import InAppNotification

    _create_in_app(
        user,
        ntype=InAppNotification.Type.SUCCESS,
        title="Subscription renewed",
        message=ctx["renewal_detail"],
    )

    sub.subscription_renewed_notified_period_end = period_end
    sub.subscription_expired_notified_at = None
    sub.subscription_expiring_notified_for_end = None
    sub.save(
        update_fields=[
            "subscription_renewed_notified_period_end",
            "subscription_expired_notified_at",
            "subscription_expiring_notified_for_end",
            "updated_at",
        ]
    )
    return True


def notify_subscription_expiring_soon(sub, *, ends_at: datetime, days_remaining: int) -> bool:
    """Reminder before trial or paid period ends."""
    user = sub.user
    if not user.is_active or not user.email:
        return False
    if sub.subscription_expiring_notified_for_end == ends_at:
        return False

    ctx = _billing_email_context(user, sub)
    ctx["days_remaining"] = days_remaining
    ctx["ends_at_display"] = _format_dt(ends_at)
    is_trial = sub.status == sub.Status.TRIAL or (
        sub.trial_ends_at and not (sub.gateway_subscription_id or "").strip()
    )
    if is_trial:
        ctx["expiring_detail"] = (
            f'Your trial ends in {days_remaining} day{"s" if days_remaining != 1 else ""} '
            f'({ctx["ends_at_display"]}). Upgrade to keep full access.'
        )
    else:
        ctx["expiring_detail"] = (
            f'Your billing period ends in {days_remaining} day{"s" if days_remaining != 1 else ""} '
            f'({ctx["ends_at_display"]}). Renew to avoid interruption.'
        )
    app_name = ctx["app_name"]

    _send_billing_email(
        user,
        subject=f"{app_name}: subscription ending soon",
        template="subscription_expiring_soon.html",
        context=ctx,
    )
    from base.models import InAppNotification

    _create_in_app(
        user,
        ntype=InAppNotification.Type.INFO,
        title="Subscription ending soon",
        message=ctx["expiring_detail"],
    )

    sub.subscription_expiring_notified_for_end = ends_at
    sub.save(update_fields=["subscription_expiring_notified_for_end", "updated_at"])
    return True


def handle_subscription_sync_notifications(sub, *, before: SubscriptionSnapshot) -> None:
    """
    After Dodo subscription webhook sync: welcome on first link, renewal when period extends.
    """
    after = snapshot_subscription(sub)
    had_gateway = bool(before.gateway_subscription_id)
    has_gateway = bool(after.gateway_subscription_id)

    if has_gateway and not sub.subscription_welcome_notified_at:
        if after.status in (sub.Status.ACTIVE, sub.Status.TRIAL) and after.plan_id:
            if not had_gateway or before.status not in (sub.Status.ACTIVE, sub.Status.TRIAL):
                notify_subscription_welcome(sub)
                return

    if (
        after.status == sub.Status.ACTIVE
        and has_gateway
        and after.current_period_end
        and before.current_period_end
        and after.current_period_end > before.current_period_end
        and sub.subscription_welcome_notified_at
    ):
        notify_subscription_renewed(sub, period_end=after.current_period_end)


def handle_payment_succeeded_notifications(sub, *, invoice_created: bool) -> None:
    """After payment.succeeded creates a new invoice."""
    if not invoice_created:
        return
    if sub.current_period_end and sub.subscription_welcome_notified_at:
        notify_subscription_renewed(sub, period_end=sub.current_period_end)


def _subscription_ends_at(sub):
    """When the current trial or paid period ends (before grace)."""
    from base.models import Subscription

    if sub.status == Subscription.Status.TRIAL and sub.trial_ends_at:
        return sub.trial_ends_at
    return sub.current_period_end


def notify_subscription_expired(sub, *, expiry_detail: str) -> bool:
    """Post-expiry email + in-app (respects billing email preference for mail)."""
    user = sub.user
    if not user.is_active or not user.email:
        return False
    if sub.subscription_expired_notified_at:
        return False

    ctx = _billing_email_context(user, sub)
    ctx["expiry_detail"] = expiry_detail
    app_name = ctx["app_name"]

    _send_billing_email(
        user,
        subject=f"{app_name}: subscription update",
        template="subscription_expired.html",
        context=ctx,
    )
    from base.models import InAppNotification

    _create_in_app(
        user,
        ntype=InAppNotification.Type.WARNING,
        title="Subscription no longer active",
        message=(
            "Your plan has expired. Open Billing to renew or upgrade and restore full access."
        ),
    )

    now = timezone.now()
    sub.subscription_expired_notified_at = now
    sub.save(update_fields=["subscription_expired_notified_at", "updated_at"])
    return True
