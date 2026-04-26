"""
Central subscription entitlement logic.

Industry-standard behavior:
- Access to paid features is tied to the current billing period end.
- After period end, apply a short grace window, then restrict paid entitlements.
- Status fields from the gateway can be stale; entitlements must still be enforced.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Optional

from django.conf import settings
from django.utils import timezone


@dataclass(frozen=True)
class Entitlements:
    is_paid_active: bool
    is_trial_active: bool
    is_expired: bool
    max_teams: int
    max_members_per_team: int
    agent_ops_limit: Optional[int]  # None = unlimited


def _grace_period() -> timedelta:
    days = int(getattr(settings, "BILLING_GRACE_DAYS", 3) or 0)
    if days < 0:
        days = 0
    return timedelta(days=days)


def _expired_caps() -> tuple[int, int, int]:
    # Conservative defaults: keep account usable for viewing, but block growth/actions.
    max_teams = int(getattr(settings, "EXPIRED_MAX_TEAMS", 1) or 1)
    max_members = int(getattr(settings, "EXPIRED_MAX_MEMBERS_PER_TEAM", 1) or 1)
    max_ops = int(getattr(settings, "EXPIRED_MAX_AGENT_OPS", 0) or 0)
    return max_teams, max_members, max_ops


def subscription_is_active_now(sub, *, now=None) -> bool:
    """
    True only when user should have paid/trial entitlements *right now*.
    This is stricter than `sub.status == active`.
    """
    if sub is None:
        return False
    now = now or timezone.now()

    if sub.status == "trial":
        if sub.trial_ends_at and now < sub.trial_ends_at:
            return True
        return False

    if sub.status != "active":
        return False

    if sub.current_period_end:
        return now < sub.current_period_end
    # If we don't have a period end, treat as not entitled (safer).
    return False


def subscription_is_expired(sub, *, now=None) -> bool:
    if sub is None:
        return True
    now = now or timezone.now()

    if sub.status == "trial":
        return bool(sub.trial_ends_at and sub.trial_ends_at <= now)

    if sub.current_period_end and (sub.current_period_end + _grace_period()) <= now:
        return True
    return False


def reconcile_subscription_status(sub, *, now=None) -> None:
    """
    Best-effort local status reconciliation when periods have clearly ended.
    Does not talk to the gateway (that belongs in sync/webhooks).
    """
    if sub is None:
        return
    now = now or timezone.now()
    if sub.status == "active" and subscription_is_expired(sub, now=now):
        try:
            sub.status = "past_due"
            sub.save(update_fields=["status", "updated_at"])
        except Exception:
            # Avoid blocking API calls due to billing state write failures
            return
    if sub.status == "trial" and subscription_is_expired(sub, now=now):
        try:
            sub.status = "canceled"
            sub.save(update_fields=["status", "updated_at"])
        except Exception:
            return


def get_entitlements_for_subscription(sub, *, now=None) -> Entitlements:
    now = now or timezone.now()
    expired = subscription_is_expired(sub, now=now)

    if not sub or expired:
        max_teams, max_members, max_ops = _expired_caps()
        return Entitlements(
            is_paid_active=False,
            is_trial_active=False,
            is_expired=True,
            max_teams=max_teams,
            max_members_per_team=max_members,
            agent_ops_limit=max_ops,
        )

    is_trial = sub.status == "trial" and sub.trial_ends_at and now < sub.trial_ends_at
    is_paid = sub.status == "active" and sub.current_period_end and now < sub.current_period_end

    # Default caps come from plan; if missing, fall back to conservative settings.
    plan = getattr(sub, "plan", None)
    max_teams = int(getattr(plan, "max_teams", None) or getattr(settings, "PLAN_MAX_TEAMS", 20))
    max_members = int(getattr(plan, "max_members", None) or 50)
    ops = getattr(plan, "max_agent_operations_per_month", None)
    agent_limit = None if ops is None else int(ops)

    return Entitlements(
        is_paid_active=bool(is_paid),
        is_trial_active=bool(is_trial),
        is_expired=False,
        max_teams=max_teams,
        max_members_per_team=max_members,
        agent_ops_limit=agent_limit,
    )

