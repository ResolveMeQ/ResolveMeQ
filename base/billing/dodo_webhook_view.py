"""
Dodo Payments Standard Webhooks receiver (subscription sync + invoice creation).

Important: never return HTTP 5xx from this view.

Django's AdminEmailHandler emails ADMINS for every response with status >= 500
(even deliberate HttpResponseServerError with no exception). Dodo also retries
on 5xx, which turns one bad delivery into an inbox flood. Other Dodo projects
typically ack with 2xx and log; this endpoint must do the same.
"""
from __future__ import annotations

import logging

from django.conf import settings
from django.db import IntegrityError, transaction
from django.http import HttpResponse, HttpResponseBadRequest
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from base.billing.exceptions import SubscriptionSyncError
from base.billing.payment_sync import apply_dodo_payment_succeeded
from base.billing.subscription_sync import apply_dodo_subscription_payload
from base.models import BillingWebhookDelivery

logger = logging.getLogger(__name__)

SUBSCRIPTION_EVENT_PREFIX = 'subscription.'
PAYMENT_SUCCEEDED = 'payment.succeeded'


def _webhook_delivery_id(request) -> str | None:
    return request.headers.get('webhook-id') or request.META.get('HTTP_WEBHOOK_ID')


def _header_map(request) -> dict[str, str]:
    return {str(k): str(v) for k, v in request.headers.items()}


def _ack(delivery_id: str | None = None, event_type: str = '') -> HttpResponse:
    """Acknowledge receipt so Dodo stops retrying and Django does not mail ADMINS."""
    if delivery_id:
        try:
            BillingWebhookDelivery.objects.create(
                delivery_id=delivery_id,
                provider=BillingWebhookDelivery.Provider.DODO,
                event_type=event_type or 'acked',
            )
        except IntegrityError:
            pass
        except Exception:
            logger.exception(
                'Dodo webhook: failed to record delivery_id=%s (still acking)',
                delivery_id,
            )
    return HttpResponse(status=200)


@method_decorator(csrf_exempt, name='dispatch')
class DodoWebhookView(View):
    """
    POST raw JSON body. Verified with DODO_PAYMENTS_WEBHOOK_KEY (Standard Webhooks).
    Handles subscription.* (sync subscription) and payment.succeeded (create invoice).
    Configure URL in Dodo dashboard: /api/billing/webhooks/dodo/
    """

    def post(self, request, *args, **kwargs):
        try:
            return self._handle_post(request)
        except Exception:
            # Last-resort safety net: never let an uncaught error become a 500 email.
            logger.exception('Dodo webhook: unhandled error')
            return HttpResponse(status=200)

    def _handle_post(self, request):
        wid = _webhook_delivery_id(request)
        if not wid:
            return HttpResponseBadRequest('missing webhook-id')

        api_key = (getattr(settings, 'DODO_PAYMENTS_API_KEY', None) or '').strip()
        wh_key = (getattr(settings, 'DODO_PAYMENTS_WEBHOOK_KEY', None) or '').strip()
        if not api_key or not wh_key:
            # Retryable ops issue: 503 so Dodo retries after keys are fixed.
            # Admin emails for this path are suppressed in logging_filters.
            logger.error('Dodo webhook: API or webhook key not configured')
            return HttpResponse(status=503)

        if BillingWebhookDelivery.objects.filter(delivery_id=wid).exists():
            return HttpResponse(status=200)

        try:
            from dodopayments import DodoPayments
        except ImportError:
            logger.exception('dodopayments not installed')
            return HttpResponse(status=503)

        try:
            raw = request.body.decode('utf-8')
            client = DodoPayments(
                bearer_token=api_key,
                environment=getattr(settings, 'DODO_PAYMENTS_ENVIRONMENT', 'test_mode'),
                webhook_key=wh_key,
            )
            event = client.webhooks.unwrap(raw, headers=_header_map(request), key=wh_key)
        except Exception:
            # Bad signature / body: 400 so Dodo does not treat it as success, but no 5xx email.
            logger.exception('Dodo webhook verification or parse failed')
            return HttpResponseBadRequest('invalid webhook')

        event_type = getattr(event, 'type', '') or ''

        if event_type == PAYMENT_SUCCEEDED:
            try:
                with transaction.atomic():
                    apply_dodo_payment_succeeded(event.data)
                    BillingWebhookDelivery.objects.create(
                        delivery_id=wid,
                        provider=BillingWebhookDelivery.Provider.DODO,
                        event_type=event_type,
                    )
            except IntegrityError:
                pass
            except Exception:
                logger.exception(
                    'Dodo webhook payment handler failed (delivery_id=%s)', wid
                )
                return _ack(wid, event_type or 'payment.failed_handler')
            return HttpResponse(status=200)

        if not event_type.startswith(SUBSCRIPTION_EVENT_PREFIX):
            return _ack(wid, event_type or 'ignored')

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
            # Permanent for this delivery: unknown/test customer, missing metadata, etc.
            logger.warning('Dodo webhook: %s (delivery_id=%s event=%s)', exc, wid, event_type)
            return _ack(wid, event_type or 'subscription.unresolved')
        except Exception:
            logger.exception('Dodo webhook handler failed (delivery_id=%s)', wid)
            return _ack(wid, event_type or 'subscription.failed_handler')

        return HttpResponse(status=200)
