"""
HTTP-boundary tests for the Dodo Payments webhook endpoint
(base/billing/dodo_webhook_view.py, POST /api/billing/webhooks/dodo/).

These tests exercise the real Standard Webhooks signature verification path
(standardwebhooks.Webhook, via the dodopayments SDK's ``client.webhooks.unwrap``)
by constructing genuinely-signed request bodies, rather than mocking the SDK.
Only external network calls (there are none in the happy path - `unwrap` verifies
locally) are avoided; no live Dodo API or shared DB is touched.

Run in isolation with:
    python manage.py test base.tests_dodo_webhook --settings=test_settings
"""
from __future__ import annotations

import base64
import json
from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from standardwebhooks import Webhook

from base.models import (
    BillingWebhookDelivery,
    Invoice,
    Plan,
    PlanGatewayProduct,
    Subscription,
)

User = get_user_model()

WEBHOOK_URL = '/api/billing/webhooks/dodo/'

# Deterministic test-only signing secret (Standard Webhooks format: whsec_<base64>).
TEST_WEBHOOK_KEY = 'whsec_' + base64.b64encode(b'test-only-signing-secret-32bytes').decode()


def _billing_address() -> dict:
    return {
        'country': 'US',
        'city': 'San Francisco',
        'state': 'CA',
        'street': '1 Main St',
        'zipcode': '94000',
    }


def _sign_headers(raw_body: str, msg_id: str, ts: datetime) -> dict:
    """Build the webhook-id/timestamp/signature headers using the real
    standardwebhooks signer, matching exactly what Dodo would send."""
    wh = Webhook(TEST_WEBHOOK_KEY)
    sig = wh.sign(msg_id=msg_id, timestamp=ts, data=raw_body)
    return {
        'HTTP_WEBHOOK_ID': msg_id,
        'HTTP_WEBHOOK_TIMESTAMP': str(int(ts.timestamp())),
        'HTTP_WEBHOOK_SIGNATURE': sig,
    }


@override_settings(
    DODO_PAYMENTS_API_KEY='test-api-key',
    DODO_PAYMENTS_WEBHOOK_KEY=TEST_WEBHOOK_KEY,
    DODO_PAYMENTS_ENVIRONMENT='test_mode',
)
class DodoWebhookViewTests(TestCase):
    """Tests for the real HTTP entrypoint, not the internal apply_* helpers."""

    def setUp(self):
        self.user = User.objects.create_user(
            email='webhook@test.com',
            username='webhookuser',
            password='test-pass-123',
        )
        self.plan = Plan.objects.create(
            name='Webhook Plan',
            slug='webhook-plan',
            max_teams=5,
            max_members=10,
            price_monthly=Decimal('10.00'),
            price_yearly=Decimal('100.00'),
        )
        PlanGatewayProduct.objects.create(
            plan=self.plan,
            gateway=PlanGatewayProduct.Gateway.DODO,
            interval=PlanGatewayProduct.Interval.MONTHLY,
            external_product_id='prod_dodo_webhook_test',
        )

    # -- payload builders -------------------------------------------------

    def _subscription_body(self, *, subscription_id='sub_webhook_test', status='active', **data_overrides) -> str:
        now = timezone.now()
        data = {
            'addons': [],
            'billing': _billing_address(),
            'cancel_at_next_billing_date': False,
            'created_at': now.isoformat(),
            'credit_entitlement_cart': [],
            'currency': 'USD',
            'customer': {
                'customer_id': 'cus_webhook_test',
                'email': self.user.email,
                'name': 'Webhook Test User',
            },
            'metadata': {'resolvemeq_user_id': str(self.user.pk)},
            'meter_credit_entitlement_cart': [],
            'meters': [],
            'next_billing_date': (now + timedelta(days=30)).isoformat(),
            'on_demand': False,
            'payment_frequency_count': 1,
            'payment_frequency_interval': 'Month',
            'previous_billing_date': now.isoformat(),
            'product_id': 'prod_dodo_webhook_test',
            'quantity': 1,
            'recurring_pre_tax_amount': 1000,
            'status': status,
            'subscription_id': subscription_id,
            'subscription_period_count': 1,
            'subscription_period_interval': 'Month',
            'tax_inclusive': True,
            'trial_period_days': 0,
        }
        data.update(data_overrides)
        event_type = {
            'active': 'subscription.active',
            'on_hold': 'subscription.on_hold',
            'cancelled': 'subscription.cancelled',
        }.get(status, 'subscription.active')
        body = {
            'business_id': 'biz_test',
            'type': event_type,
            'timestamp': now.isoformat(),
            'data': data,
        }
        return json.dumps(body)

    def _payment_body(self, *, subscription_id='sub_webhook_test', payment_id='pay_webhook_test', **data_overrides) -> str:
        now = timezone.now()
        data = {
            'billing': _billing_address(),
            'brand_id': 'brand_test',
            'business_id': 'biz_test',
            'created_at': now.isoformat(),
            'currency': 'USD',
            'customer': {
                'customer_id': 'cus_webhook_test',
                'email': self.user.email,
                'name': 'Webhook Test User',
            },
            'digital_products_delivered': False,
            'disputes': [],
            'metadata': {},
            'payment_id': payment_id,
            'refunds': [],
            'settlement_amount': 1999,
            'settlement_currency': 'USD',
            'total_amount': 1999,
            'subscription_id': subscription_id,
            'invoice_url': 'https://dodo.example/invoice/1',
        }
        data.update(data_overrides)
        body = {
            'business_id': 'biz_test',
            'type': 'payment.succeeded',
            'timestamp': now.isoformat(),
            'data': data,
        }
        return json.dumps(body)

    # -- request helpers ----------------------------------------------------

    def _post_signed(self, raw_body: str, msg_id: str, ts: datetime | None = None):
        ts = ts or timezone.now()
        headers = _sign_headers(raw_body, msg_id, ts)
        return self.client.post(
            WEBHOOK_URL, data=raw_body, content_type='application/json', **headers
        )

    def _post_unsigned(self, raw_body: str, msg_id: str, ts: datetime | None = None, bad_signature: str | None = None):
        ts = ts or timezone.now()
        headers = {
            'HTTP_WEBHOOK_ID': msg_id,
            'HTTP_WEBHOOK_TIMESTAMP': str(int(ts.timestamp())),
            'HTTP_WEBHOOK_SIGNATURE': bad_signature or 'v1,AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=',
        }
        return self.client.post(
            WEBHOOK_URL, data=raw_body, content_type='application/json', **headers
        )

    # -- 1. valid signature is accepted and processed ------------------------

    def test_validly_signed_subscription_event_is_accepted_and_processed(self):
        body = self._subscription_body()
        resp = self._post_signed(body, 'msg_sub_valid_1')
        self.assertEqual(resp.status_code, 200)

        sub = Subscription.objects.get(user=self.user)
        self.assertEqual(sub.gateway_subscription_id, 'sub_webhook_test')
        self.assertEqual(sub.status, Subscription.Status.ACTIVE)
        self.assertTrue(
            BillingWebhookDelivery.objects.filter(delivery_id='msg_sub_valid_1').exists()
        )

    def test_validly_signed_payment_succeeded_event_creates_invoice(self):
        Subscription.objects.create(
            user=self.user,
            plan=self.plan,
            status=Subscription.Status.ACTIVE,
            gateway=PlanGatewayProduct.Gateway.DODO,
            gateway_subscription_id='sub_webhook_test',
            gateway_customer_id='cus_webhook_test',
        )
        body = self._payment_body()
        resp = self._post_signed(body, 'msg_pay_valid_1')
        self.assertEqual(resp.status_code, 200)

        inv = Invoice.objects.get(gateway_payment_id='pay_webhook_test')
        self.assertEqual(inv.amount, Decimal('19.99'))
        self.assertTrue(
            BillingWebhookDelivery.objects.filter(delivery_id='msg_pay_valid_1').exists()
        )

    # -- 2. invalid signature is rejected, not processed ----------------------

    def test_invalid_signature_rejected_and_not_processed(self):
        body = self._subscription_body(subscription_id='sub_should_not_exist')
        resp = self._post_unsigned(body, 'msg_sub_bad_sig_1')
        self.assertEqual(resp.status_code, 400)

        self.assertFalse(Subscription.objects.filter(user=self.user).exists())
        self.assertFalse(
            BillingWebhookDelivery.objects.filter(delivery_id='msg_sub_bad_sig_1').exists()
        )

    def test_missing_signature_headers_rejected(self):
        body = self._subscription_body(subscription_id='sub_should_not_exist_2')
        resp = self.client.post(
            WEBHOOK_URL,
            data=body,
            content_type='application/json',
            HTTP_WEBHOOK_ID='msg_sub_no_sig_1',
        )
        # No webhook-signature/timestamp headers at all -> verification fails.
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(Subscription.objects.filter(user=self.user).exists())

    # -- 3. malformed JSON body doesn't crash the endpoint ---------------------

    def test_malformed_json_body_returns_4xx_not_500(self):
        garbage = '{not valid json::'
        ts = timezone.now()
        # Sign over the garbage bytes themselves so verification succeeds and we
        # specifically exercise the json.loads failure path inside unwrap().
        headers = _sign_headers(garbage, 'msg_garbage_1', ts)
        resp = self.client.post(
            WEBHOOK_URL, data=garbage, content_type='application/json', **headers
        )
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(
            BillingWebhookDelivery.objects.filter(delivery_id='msg_garbage_1').exists()
        )

    def test_missing_webhook_id_header_returns_400(self):
        body = self._subscription_body()
        resp = self.client.post(WEBHOOK_URL, data=body, content_type='application/json')
        self.assertEqual(resp.status_code, 400)

    # -- 4. idempotency: same delivery_id twice only processes once -----------

    def test_duplicate_delivery_id_is_a_no_op_second_time(self):
        body = self._subscription_body()
        resp1 = self._post_signed(body, 'msg_sub_dup_1')
        self.assertEqual(resp1.status_code, 200)
        self.assertEqual(
            BillingWebhookDelivery.objects.filter(delivery_id='msg_sub_dup_1').count(), 1
        )
        sub = Subscription.objects.get(user=self.user)
        updated_at_after_first = sub.updated_at

        # Re-deliver the exact same webhook-id (Dodo retry semantics).
        resp2 = self._post_signed(body, 'msg_sub_dup_1')
        self.assertEqual(resp2.status_code, 200)

        self.assertEqual(
            BillingWebhookDelivery.objects.filter(delivery_id='msg_sub_dup_1').count(), 1
        )
        sub.refresh_from_db()
        self.assertEqual(sub.updated_at, updated_at_after_first)

    # -- 5. duplicate payment.succeeded deliveries for same gateway_payment_id --

    def test_duplicate_payment_succeeded_deliveries_do_not_double_create_invoice(self):
        """
        Two *different* webhook deliveries (distinct delivery_id, as Dodo would
        send on a legitimate re-notify) referencing the same underlying payment
        must not create two Invoice rows.

        The outer BillingWebhookDelivery.delivery_id dedup check in
        DodoWebhookView.post is a check-then-act race (the `.exists()` check
        happens outside the atomic block), but Invoice.gateway_payment_id has a
        DB-level unique constraint (see base/models.py) and
        apply_dodo_payment_succeeded() catches IntegrityError, so this should
        NOT double-create even though the outer dedup alone would not prevent it.
        """
        Subscription.objects.create(
            user=self.user,
            plan=self.plan,
            status=Subscription.Status.ACTIVE,
            gateway=PlanGatewayProduct.Gateway.DODO,
            gateway_subscription_id='sub_webhook_test',
            gateway_customer_id='cus_webhook_test',
        )
        body1 = self._payment_body(payment_id='pay_dup_race_1')
        body2 = self._payment_body(payment_id='pay_dup_race_1')

        resp1 = self._post_signed(body1, 'msg_pay_dup_a')
        resp2 = self._post_signed(body2, 'msg_pay_dup_b')

        self.assertEqual(resp1.status_code, 200)
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(
            Invoice.objects.filter(gateway_payment_id='pay_dup_race_1').count(), 1
        )
        # Both deliveries are individually recorded (different delivery_ids).
        self.assertEqual(
            BillingWebhookDelivery.objects.filter(
                delivery_id__in=['msg_pay_dup_a', 'msg_pay_dup_b']
            ).count(),
            2,
        )
