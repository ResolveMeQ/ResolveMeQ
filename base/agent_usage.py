"""
Monthly AI agent operation quotas per billing account (subscription owner).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

from django.conf import settings
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


@dataclass
class AgentQuotaResult:
    allowed: bool
    used: int
    limit: Optional[int]


def get_billing_user_for_ticket(ticket) -> Any:
    """Account owner for quota: team owner when set, else the ticket creator.

    Team.owner is nullable; if the ticket has a team but no owner, bill against ticket.user.
    """
    if ticket.team_id:
        owner = ticket.team.owner
        if owner is not None:
            return owner
    return ticket.user


def resolve_usage_period(user, now=None):
    """
    Return [period_start, period_end) for usage accounting.
    Prefer subscription billing window when set and current; else calendar month (UTC).
    """
    from base.models import Subscription

    now = now or timezone.now()
    try:
        sub = Subscription.objects.select_related('plan').get(user=user)
    except Subscription.DoesNotExist:
        sub = None

    if sub:
        from base.billing.entitlements import subscription_is_active_now
        if subscription_is_active_now(sub, now=now) and sub.current_period_start and sub.current_period_end:
            if sub.current_period_start <= now < sub.current_period_end:
                return sub.current_period_start, sub.current_period_end

    from dateutil.relativedelta import relativedelta

    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end = start + relativedelta(months=1)
    return start, end


def get_effective_agent_ops_limit(user) -> Optional[int]:
    """
    Monthly cap for this billing user, or None for unlimited.
    """
    from base.models import Subscription

    try:
        sub = Subscription.objects.select_related('plan').get(user=user)
    except Subscription.DoesNotExist:
        return getattr(settings, 'DEFAULT_AGENT_OPERATIONS_PER_MONTH', 500)

    if not sub.plan_id:
        return getattr(settings, 'DEFAULT_AGENT_OPERATIONS_PER_MONTH', 500)

    plan = sub.plan
    from base.billing.entitlements import get_entitlements_for_subscription, reconcile_subscription_status
    reconcile_subscription_status(sub)
    ent = get_entitlements_for_subscription(sub)
    if ent.is_expired:
        # Industry default: disable paid AI operations when expired.
        return ent.agent_ops_limit

    if plan.max_agent_operations_per_month is None:
        return None

    return int(plan.max_agent_operations_per_month)


def try_consume_agent_operation(billing_user) -> AgentQuotaResult:
    limit = get_effective_agent_ops_limit(billing_user)
    if limit is None:
        return AgentQuotaResult(allowed=True, used=0, limit=None)

    if limit <= 0:
        return AgentQuotaResult(allowed=False, used=0, limit=0)

    period_start, period_end = resolve_usage_period(billing_user)

    from base.models import AgentUsageMonthly

    with transaction.atomic():
        row, _ = AgentUsageMonthly.objects.select_for_update().get_or_create(
            user=billing_user,
            period_start=period_start,
            defaults={'period_end': period_end, 'operations_used': 0},
        )
        update_fields = []
        if row.period_end != period_end:
            row.period_end = period_end
            update_fields.append('period_end')
        if row.operations_used >= limit:
            return AgentQuotaResult(allowed=False, used=row.operations_used, limit=limit)

        row.operations_used += 1
        update_fields.extend(['operations_used', 'updated_at'])
        row.save(update_fields=update_fields)
        return AgentQuotaResult(allowed=True, used=row.operations_used, limit=limit)


def refund_agent_operation(billing_user) -> None:
    if billing_user is None:
        return

    limit = get_effective_agent_ops_limit(billing_user)
    if limit is None or limit <= 0:
        return

    period_start, _ = resolve_usage_period(billing_user)
    from base.models import AgentUsageMonthly

    with transaction.atomic():
        row = (
            AgentUsageMonthly.objects.select_for_update()
            .filter(user=billing_user, period_start=period_start)
            .first()
        )
        if row and row.operations_used > 0:
            row.operations_used -= 1
            row.save(update_fields=['operations_used', 'updated_at'])


def get_agent_usage_snapshot(user) -> dict[str, Any]:
    limit = get_effective_agent_ops_limit(user)
    if limit is None:
        return {
            'agent_operations_used': None,
            'agent_operations_limit': None,
            'agent_operations_unlimited': True,
        }

    period_start, period_end = resolve_usage_period(user)
    from base.models import AgentUsageMonthly

    row = AgentUsageMonthly.objects.filter(user=user, period_start=period_start).first()
    used = row.operations_used if row else 0
    return {
        'agent_operations_used': used,
        'agent_operations_limit': limit,
        'agent_operations_unlimited': False,
        'agent_period_ends_at': period_end.isoformat(),
    }
