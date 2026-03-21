"""
Dodo Payments Standard Webhooks receiver (subscription sync).
"""
from __future__ import annotations

import logging

from django.conf import settings
from django.db import IntegrityError, transaction
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseServerError
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from base.billing.exceptions import SubscriptionSyncError
from base.billing.subscription_sync import apply_dodo_subscription_payload
from base.models import BillingWebhookDelivery

logger = logging.getLogger(__name__)

SUBSCRIPTION_EVENT_PREFIX = 'subscription.'


def _webhook_delivery_id(request) -> str | None:
    return request.headers.get('webhook-id') or request.META.get('HTTP_WEBHOOK_ID')


def _header_map(request) -> dict[str, str]:
    return {str(k): str(v) for k, v in request.headers.items()}


@method_decorator(csrf_exempt, name='dispatch')
class DodoWebhookView(View):
    """
    POST raw JSON body. Verified with DODO_PAYMENTS_WEBHOOK_KEY (Standard Webhooks).
    Configure URL in Dodo dashboard: /api/billing/webhooks/dodo/
    """

    def post(self, request, *args, **kwargs):
        wid = _webhook_delivery_id(request)
        if not wid:
            return HttpResponseBadRequest('missing webhook-id')

        api_key = (getattr(settings, 'DODO_PAYMENTS_API_KEY', None) or '').strip()
        wh_key = (getattr(settings, 'DODO_PAYMENTS_WEBHOOK_KEY', None) or '').strip()
        if not api_key or not wh_key:
            logger.error('Dodo webhook: API or webhook key not configured')
            return HttpResponseServerError('billing not configured')

        if BillingWebhookDelivery.objects.filter(delivery_id=wid).exists():
            return HttpResponse(status=200)

        try:
            from dodopayments import DodoPayments
        except ImportError:
            logger.exception('dodopayments not installed')
            return HttpResponseServerError('billing sdk missing')

        try:
            raw = request.body.decode('utf-8')
            client = DodoPayments(
                bearer_token=api_key,
                environment=getattr(settings, 'DODO_PAYMENTS_ENVIRONMENT', 'test_mode'),
                webhook_key=wh_key,
            )
            event = client.webhooks.unwrap(raw, headers=_header_map(request), key=wh_key)
        except Exception:
            logger.exception('Dodo webhook verification or parse failed')
            return HttpResponseBadRequest('invalid webhook')

        event_type = getattr(event, 'type', '') or ''
        if not event_type.startswith(SUBSCRIPTION_EVENT_PREFIX):
            return HttpResponse(status=200)

        try:
            with transaction.atomic():
                if not apply_dodo_subscription_payload(event.data):
                    raise SubscriptionSyncError('user could not be resolved from payload')
                BillingWebhookDelivery.objects.create(
                    delivery_id=wid,
                    provider=BillingWebhookDelivery.Provider.DODO,
                    event_type=event_type,
                )
        except IntegrityError:
            return HttpResponse(status=200)
        except SubscriptionSyncError as exc:
            logger.warning('Dodo webhook: %s (delivery_id=%s)', exc, wid)
            return HttpResponseServerError('sync failed')
        except Exception:
            logger.exception('Dodo webhook handler failed (delivery_id=%s)', wid)
            return HttpResponseServerError('handler error')

        return HttpResponse(status=200)
