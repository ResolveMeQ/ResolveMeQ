"""
Apply Dodo Payments subscription payloads to local Subscription rows.
"""
from __future__ import annotations

import logging
from typing import Any

from django.contrib.auth import get_user_model

from base.models import PlanGatewayProduct, Subscription

logger = logging.getLogger(__name__)
User = get_user_model()


def _map_dodo_status(status: str) -> str:
    return {
        'pending': Subscription.Status.TRIAL,
        'active': Subscription.Status.ACTIVE,
        'on_hold': Subscription.Status.PAST_DUE,
        'cancelled': Subscription.Status.CANCELED,
        'failed': Subscription.Status.PAST_DUE,
        'expired': Subscription.Status.CANCELED,
    }.get(status, Subscription.Status.ACTIVE)


def _resolve_user(sub_payload: Any):
    meta = sub_payload.metadata or {}
    uid = meta.get('resolvemeq_user_id')
    if uid:
        user = User.objects.filter(pk=uid).first()
        if user:
            return user
    email = getattr(sub_payload.customer, 'email', None) if sub_payload.customer else None
    if email:
        user = User.objects.filter(email__iexact=email.strip()).first()
        if user:
            return user
    return None


def _resolve_plan(sub_payload: Any):
    mapping = PlanGatewayProduct.objects.filter(
        gateway=PlanGatewayProduct.Gateway.DODO,
        external_product_id=sub_payload.product_id,
    ).select_related('plan').first()
    return mapping.plan if mapping else None


def apply_dodo_subscription_payload(sub_payload: Any) -> bool:
    """
    Upsert Subscription for this user from a Dodo subscription object (webhook .data).
    Returns True if a row was updated, False if the user could not be resolved.
    """
    user = _resolve_user(sub_payload)
    if not user:
        logger.warning(
            'Dodo webhook: could not resolve user (subscription_id=%s, product_id=%s)',
            getattr(sub_payload, 'subscription_id', None),
            getattr(sub_payload, 'product_id', None),
        )
        return False

    plan = _resolve_plan(sub_payload)
    status = _map_dodo_status(sub_payload.status)
    customer_id = (
        sub_payload.customer.customer_id if sub_payload.customer else ''
    )
    gateway_sub_id = sub_payload.subscription_id

    sub, _ = Subscription.objects.select_for_update().get_or_create(
        user=user,
        defaults={'status': Subscription.Status.ACTIVE},
    )
    sub.gateway = PlanGatewayProduct.Gateway.DODO
    if customer_id:
        sub.gateway_customer_id = customer_id
    if gateway_sub_id:
        sub.gateway_subscription_id = gateway_sub_id
    if plan is not None:
        sub.plan = plan
    sub.status = status
    sub.current_period_start = sub_payload.previous_billing_date
    sub.current_period_end = sub_payload.next_billing_date
    sub.save(
        update_fields=[
            'gateway',
            'gateway_customer_id',
            'gateway_subscription_id',
            'plan',
            'status',
            'current_period_start',
            'current_period_end',
            'updated_at',
        ]
    )
    return True
