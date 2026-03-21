"""
Create local Invoice records from Dodo payment.succeeded webhook events
or by syncing succeeded payments from the Dodo API.
"""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from django.db import IntegrityError
from django.utils import timezone

from base.models import Invoice, Subscription

logger = logging.getLogger(__name__)


def sync_invoices_from_dodo(user) -> int:
    """
    Fetch succeeded payments from Dodo for the user's subscription (or customer)
    and create local Invoice (transaction) records for any that don't exist.
    Returns the number of new invoices created. Run when loading Transaction
    History so we persist all user transactions for tracking and audit.
    Uses customers.list(email=...) to backfill gateway ids when Subscription
    has none (e.g. webhooks never fired).
    """
    try:
        sub = Subscription.objects.filter(user=user).first()
    except Exception:
        return 0
    if not sub:
        return 0

    subscription_id = (sub.gateway_subscription_id or '').strip()
    customer_id = (sub.gateway_customer_id or '').strip()
    if not subscription_id and not customer_id:
        customer_id = _resolve_customer_id_from_email(user, sub)
        if not customer_id:
            return 0

    try:
        from base.billing.gateways.factory import get_billing_gateway
        gateway = get_billing_gateway()
    except Exception as e:
        logger.debug('sync_invoices_from_dodo: gateway unavailable: %s', e)
        return 0

    if getattr(gateway, 'code', None) != 'dodo':
        return 0

    client = getattr(gateway, 'client', None)
    if not client or not hasattr(client, 'payments'):
        return 0

    created_count = 0
    list_kwargs = {'status': 'succeeded', 'page_size': 50}
    if subscription_id:
        list_kwargs['subscription_id'] = subscription_id
    elif customer_id:
        list_kwargs['customer_id'] = customer_id

    try:
        paginator = client.payments.list(**list_kwargs)
        for page in paginator:
            items = getattr(page, 'items', None) or getattr(page, 'data', None) or []
            for p in items:
                payment_id = getattr(p, 'payment_id', None) or ''
                if not payment_id:
                    continue
                if Invoice.objects.filter(gateway_payment_id=payment_id).exists():
                    continue
                total_minor = getattr(p, 'total_amount', 0) or 0
                amount = Decimal(total_minor) / 100
                currency = getattr(p, 'currency', 'usd') or 'usd'
                currency_upper = str(currency).upper() if len(str(currency)) == 3 else 'USD'
                created_at = getattr(p, 'created_at', None) or timezone.now()
                invoice_url = getattr(p, 'invoice_url', None) or ''
                create_kwargs = {
                    'subscription': sub,
                    'amount': amount,
                    'currency': currency_upper,
                    'status': 'paid',
                    'period_start': sub.current_period_start,
                    'period_end': sub.current_period_end,
                    'gateway_payment_id': payment_id,
                    'invoice_url': invoice_url or None,
                    'pricing_type': 'subscription',
                }
                try:
                    inv = Invoice.objects.create(**create_kwargs)
                    if created_at and inv.created_at != created_at:
                        Invoice.objects.filter(pk=inv.pk).update(created_at=created_at)
                    created_count += 1
                    logger.info('Sync: created invoice %s for payment %s', inv.id, payment_id)
                except IntegrityError:
                    pass
            if not items:
                break
    except Exception as e:
        logger.warning('sync_invoices_from_dodo failed: %s', e)
    return created_count


def _resolve_customer_id_from_email(user, sub: Subscription) -> str:
    """
    Look up Dodo customer by user email and backfill Subscription with
    gateway_customer_id and optionally gateway_subscription_id.
    Returns customer_id if found, else empty string.
    """
    email = getattr(user, 'email', None) or ''
    email = (email or '').strip()
    if not email:
        return ''

    try:
        from base.billing.gateways.factory import get_billing_gateway
        gateway = get_billing_gateway()
    except Exception:
        return ''
    if getattr(gateway, 'code', None) != 'dodo':
        return ''
    client = getattr(gateway, 'client', None)
    if not client or not hasattr(client, 'customers'):
        return ''

    try:
        paginator = client.customers.list(email=email, page_size=10)
        for page in paginator:
            items = getattr(page, 'items', None) or getattr(page, 'data', None) or []
            for c in items:
                cid = getattr(c, 'customer_id', None) or ''
                if cid:
                    update_fields = ['gateway_customer_id', 'updated_at']
                    sub.gateway_customer_id = cid
                    # Try to find subscription for this customer and backfill
                    if client.subscriptions and not (sub.gateway_subscription_id or '').strip():
                        try:
                            sub_pages = client.subscriptions.list(customer_id=cid, status='active', page_size=5)
                            for sp in sub_pages:
                                sp_items = getattr(sp, 'items', None) or getattr(sp, 'data', None) or []
                                for s in sp_items:
                                    sid = getattr(s, 'subscription_id', None) or ''
                                    if sid:
                                        sub.gateway_subscription_id = sid
                                        update_fields.append('gateway_subscription_id')
                                        break
                                if sp_items:
                                    break
                        except Exception:
                            pass
                    sub.save(update_fields=update_fields)
                    logger.info('Backfilled gateway_customer_id=%s for user %s from email lookup', cid, user.id)
                    return cid
            if not items:
                break
    except Exception as e:
        logger.warning('_resolve_customer_id_from_email failed: %s', e)
    return ''


def apply_dodo_payment_succeeded(payment_data: Any) -> bool:
    """
    Create an Invoice from a Dodo payment.succeeded event.
    Returns True if an invoice was created or already existed, False if we couldn't resolve the subscription.
    """
    subscription_id = getattr(payment_data, 'subscription_id', None)
    if not subscription_id:
        logger.debug('Dodo payment.succeeded: no subscription_id, skipping invoice creation')
        return True

    sub = Subscription.objects.filter(gateway_subscription_id=subscription_id).first()
    if not sub:
        logger.warning(
            'Dodo payment.succeeded: no subscription found for gateway_subscription_id=%s',
            subscription_id,
        )
        return False

    payment_id = getattr(payment_data, 'payment_id', None) or ''
    if payment_id and hasattr(Invoice, 'gateway_payment_id'):
        if Invoice.objects.filter(gateway_payment_id=payment_id).exists():
            return True

    total_minor = getattr(payment_data, 'total_amount', 0) or 0
    amount = Decimal(total_minor) / 100
    currency = getattr(payment_data, 'currency', 'usd') or 'usd'
    currency_upper = str(currency).upper() if len(str(currency)) == 3 else 'USD'

    created_at = getattr(payment_data, 'created_at', None) or timezone.now()
    invoice_url = getattr(payment_data, 'invoice_url', None) or ''

    create_kwargs = {
        'subscription': sub,
        'amount': amount,
        'currency': currency_upper,
        'status': 'paid',
        'period_start': sub.current_period_start,
        'period_end': sub.current_period_end,
        'pricing_type': 'subscription',
    }
    if hasattr(Invoice, 'gateway_payment_id'):
        create_kwargs['gateway_payment_id'] = payment_id
    if hasattr(Invoice, 'invoice_url'):
        create_kwargs['invoice_url'] = invoice_url

    try:
        inv = Invoice.objects.create(**create_kwargs)
        if created_at and inv.created_at != created_at:
            Invoice.objects.filter(pk=inv.pk).update(created_at=created_at)
        logger.info('Dodo payment.succeeded: created invoice %s for subscription %s', inv.id, subscription_id)
        return True
    except IntegrityError:
        return True
