"""
Staff / complimentary subscription grants (no Dodo charge).
Used by the REST staff endpoint and the Django Admin grant tool.
"""
from __future__ import annotations

import logging

from dateutil.relativedelta import relativedelta
from django.utils import timezone

from base.models import InAppNotification, Plan, Subscription, SubscriptionGrantLog
from base.billing.subscription_notifications import notify_staff_subscription_granted

logger = logging.getLogger(__name__)


def apply_staff_subscription_grant(
    *,
    recipient,
    plan: Plan,
    months_valid: int,
    clear_gateway: bool,
    note: str,
    granted_by,
) -> Subscription:
    """
    Update or create ``Subscription`` for ``recipient``, append ``SubscriptionGrantLog``,
    and best-effort in-app notification. Does not call Dodo.

    ``months_valid`` extends paid period or trial window (1–60).
    """
    months_valid = max(1, min(60, int(months_valid)))
    note = (note or "").strip()
    now = timezone.now()

    sub, _created = Subscription.objects.get_or_create(
        user=recipient,
        defaults={"status": Subscription.Status.ACTIVE},
    )

    period_start = None
    period_end = None
    trial_ends = None
    status_after = Subscription.Status.ACTIVE

    if plan.is_trial:
        status_after = Subscription.Status.TRIAL
        sub.status = Subscription.Status.TRIAL
        sub.plan = plan
        sub.trial_ends_at = now + relativedelta(months=months_valid)
        sub.current_period_start = None
        sub.current_period_end = None
        trial_ends = sub.trial_ends_at
    else:
        sub.status = Subscription.Status.ACTIVE
        sub.plan = plan
        sub.trial_ends_at = None
        sub.current_period_start = now
        sub.current_period_end = now + relativedelta(months=months_valid)
        period_start = sub.current_period_start
        period_end = sub.current_period_end
        status_after = Subscription.Status.ACTIVE

    if clear_gateway:
        sub.gateway = ""
        sub.gateway_customer_id = ""
        sub.gateway_subscription_id = ""

    sub.subscription_expired_notified_at = None

    sub.save(
        update_fields=[
            "plan",
            "status",
            "trial_ends_at",
            "current_period_start",
            "current_period_end",
            "gateway",
            "gateway_customer_id",
            "gateway_subscription_id",
            "subscription_expired_notified_at",
            "updated_at",
        ]
    )

    SubscriptionGrantLog.objects.create(
        recipient=recipient,
        granted_by=granted_by,
        subscription=sub,
        plan=plan,
        status_after=status_after,
        period_start=period_start,
        period_end=period_end,
        trial_ends_at=trial_ends,
        cleared_gateway=clear_gateway,
        months_applied=months_valid,
        note=note,
    )

    try:
        InAppNotification.objects.create(
            user=recipient,
            type=InAppNotification.Type.SUCCESS,
            title="Your subscription was updated",
            message=(
                f'Your workspace plan is now "{plan.name}". '
                f"Open Billing to see details."
            ),
            link="/billing",
        )
    except Exception as exc:
        logger.warning("Staff grant: in-app notify failed for %s: %s", recipient.id, exc)

    try:
        notify_staff_subscription_granted(sub, note=note)
    except Exception as exc:
        logger.warning("Staff grant: email notify failed for %s: %s", recipient.id, exc)

    logger.info(
        "Staff subscription grant: recipient=%s plan=%s months=%s by=%s",
        recipient.id,
        plan.slug,
        months_valid,
        getattr(granted_by, "id", None),
    )
    return sub
