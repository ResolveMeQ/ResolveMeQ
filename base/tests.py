from decimal import Decimal
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.db import transaction
from django.test import TestCase, override_settings
from django.utils import timezone

from base.billing.exceptions import BillingConfigurationError
from base.billing.gateways.factory import get_billing_gateway
from base.billing.money import decimal_to_minor_units
from base.billing.subscription_sync import apply_dodo_subscription_payload
from base.models import Plan, PlanGatewayProduct, Subscription

User = get_user_model()


class BillingMoneyTests(TestCase):
    def test_decimal_to_minor_units_usd(self):
        self.assertEqual(decimal_to_minor_units(Decimal('19.99')), 1999)
        self.assertEqual(decimal_to_minor_units(Decimal('0')), 0)

    def test_negative_amount_raises(self):
        with self.assertRaises(ValueError):
            decimal_to_minor_units(Decimal('-0.01'))


class ApplyDodoSubscriptionPayloadTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='sub@test.com',
            username='subtest',
            password='test-pass-123',
        )
        self.plan = Plan.objects.create(
            name='Test Plan',
            slug='test-plan-billing',
            max_teams=5,
            max_members=10,
            price_monthly=Decimal('10.00'),
            price_yearly=Decimal('100.00'),
        )
        PlanGatewayProduct.objects.create(
            plan=self.plan,
            gateway=PlanGatewayProduct.Gateway.DODO,
            interval=PlanGatewayProduct.Interval.MONTHLY,
            external_product_id='prod_dodo_test_1',
        )

    def _payload(self, **kwargs):
        now = timezone.now()
        defaults = {
            'metadata': {'resolvemeq_user_id': str(self.user.pk)},
            'customer': SimpleNamespace(customer_id='cus_test_1', email='sub@test.com'),
            'product_id': 'prod_dodo_test_1',
            'subscription_id': 'sub_dodo_test_1',
            'status': 'active',
            'previous_billing_date': now,
            'next_billing_date': now,
        }
        defaults.update(kwargs)
        return SimpleNamespace(**defaults)

    def test_resolves_user_from_metadata_and_upserts_subscription(self):
        with transaction.atomic():
            ok = apply_dodo_subscription_payload(self._payload())
        self.assertTrue(ok)
        sub = Subscription.objects.get(user=self.user)
        self.assertEqual(sub.gateway, PlanGatewayProduct.Gateway.DODO)
        self.assertEqual(sub.gateway_subscription_id, 'sub_dodo_test_1')
        self.assertEqual(sub.gateway_customer_id, 'cus_test_1')
        self.assertEqual(sub.plan_id, self.plan.id)
        self.assertEqual(sub.status, Subscription.Status.ACTIVE)

    def test_resolves_user_from_email_when_metadata_missing(self):
        with transaction.atomic():
            ok = apply_dodo_subscription_payload(
                self._payload(
                    metadata={},
                    customer=SimpleNamespace(customer_id='cus_test_2', email='Sub@Test.com'),
                )
            )
        self.assertTrue(ok)
        sub = Subscription.objects.get(user=self.user)
        self.assertEqual(sub.gateway_customer_id, 'cus_test_2')

    def test_maps_dodo_status_on_hold_to_past_due(self):
        with transaction.atomic():
            ok = apply_dodo_subscription_payload(self._payload(status='on_hold'))
        self.assertTrue(ok)
        sub = Subscription.objects.get(user=self.user)
        self.assertEqual(sub.status, Subscription.Status.PAST_DUE)

    def test_returns_false_when_user_cannot_be_resolved(self):
        with transaction.atomic():
            ok = apply_dodo_subscription_payload(
                self._payload(
                    metadata={},
                    customer=SimpleNamespace(customer_id='x', email='unknown@example.com'),
                )
            )
        self.assertFalse(ok)
        self.assertFalse(Subscription.objects.filter(user=self.user).exists())


class BillingGatewayFactoryTests(TestCase):
    @override_settings(DODO_PAYMENTS_API_KEY='', BILLING_GATEWAY='dodo')
    def test_dodo_requires_api_key(self):
        with self.assertRaises(BillingConfigurationError):
            get_billing_gateway()

    @override_settings(BILLING_GATEWAY='not_a_real_gateway')
    def test_unknown_gateway_raises(self):
        with self.assertRaises(BillingConfigurationError):
            get_billing_gateway()
