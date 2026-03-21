from __future__ import annotations

from decimal import Decimal

from django.conf import settings

from base.billing.gateways.factory import get_billing_gateway
from base.billing.money import decimal_to_minor_units
from base.models import Plan, PlanGatewayProduct


def plan_price_for_interval(plan: Plan, interval: str) -> Decimal:
    if interval == PlanGatewayProduct.Interval.MONTHLY:
        return plan.price_monthly
    if interval == PlanGatewayProduct.Interval.YEARLY:
        return plan.price_yearly
    raise ValueError(f'Unknown interval: {interval!r}')


def sync_dodo_products_for_plan(plan: Plan) -> list[PlanGatewayProduct]:
    """
    Ensure Dodo subscription products exist for this plan (monthly/yearly when price > 0).
    Skips intervals that already have a PlanGatewayProduct row.
    """
    gateway = get_billing_gateway()
    if gateway.code != PlanGatewayProduct.Gateway.DODO:
        raise ValueError('sync_dodo_products_for_plan requires BILLING_GATEWAY=dodo')

    currency = getattr(settings, 'BILLING_DEFAULT_CURRENCY', 'USD')
    tax_category = getattr(settings, 'BILLING_TAX_CATEGORY', 'saas')
    out: list[PlanGatewayProduct] = []

    for interval in (
        PlanGatewayProduct.Interval.MONTHLY,
        PlanGatewayProduct.Interval.YEARLY,
    ):
        amount = plan_price_for_interval(plan, interval)
        if amount <= 0:
            continue

        existing = PlanGatewayProduct.objects.filter(
            plan=plan,
            gateway=PlanGatewayProduct.Gateway.DODO,
            interval=interval,
        ).first()
        if existing:
            out.append(existing)
            continue

        ext_id = gateway.create_subscription_product(
            plan=plan,
            interval=interval,
            amount_minor=decimal_to_minor_units(amount),
            currency=currency,
            tax_category=tax_category,
        )
        row = PlanGatewayProduct.objects.create(
            plan=plan,
            gateway=PlanGatewayProduct.Gateway.DODO,
            interval=interval,
            external_product_id=ext_id,
        )
        out.append(row)

    return out
