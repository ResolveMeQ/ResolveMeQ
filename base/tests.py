from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import httpx
import dodopayments
from django.contrib.auth import get_user_model
from django.db import transaction
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from base.billing.exceptions import BillingConfigurationError
from base.billing.gateways.factory import get_billing_gateway
from base.billing.money import decimal_to_minor_units
from base.billing.entitlements import (
    effective_subscription_expiry_at,
    infer_billing_interval_from_subscription_period,
    subscription_is_expired,
)
from base.billing.subscription_sync import apply_dodo_subscription_payload
from base.agent_usage import (
    get_effective_agent_ops_limit,
    refund_agent_operation,
    try_consume_agent_operation,
)
from base.models import AgentUsageMonthly, Plan, PlanGatewayProduct, Subscription, SubscriptionGrantLog, InAppNotification

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

    @patch('base.billing.subscription_notifications.dispatch_send_email_with_template')
    def test_resolves_user_from_metadata_and_upserts_subscription(self, mock_dispatch):
        with transaction.atomic():
            ok = apply_dodo_subscription_payload(self._payload())
        self.assertTrue(ok)
        sub = Subscription.objects.get(user=self.user)
        self.assertEqual(sub.gateway, PlanGatewayProduct.Gateway.DODO)
        self.assertEqual(sub.gateway_subscription_id, 'sub_dodo_test_1')
        self.assertEqual(sub.gateway_customer_id, 'cus_test_1')
        self.assertEqual(sub.plan_id, self.plan.id)
        self.assertEqual(sub.status, Subscription.Status.ACTIVE)

    @patch('base.billing.subscription_notifications.dispatch_send_email_with_template')
    def test_resolves_user_from_email_when_metadata_missing(self, mock_dispatch):
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

    @patch('base.billing.subscription_notifications.dispatch_send_email_with_template')
    def test_maps_dodo_status_on_hold_to_past_due(self, mock_dispatch):
        now = timezone.now()
        with transaction.atomic():
            ok = apply_dodo_subscription_payload(
                self._payload(
                    status='active',
                    next_billing_date=now + timedelta(days=30),
                )
            )
        self.assertTrue(ok)
        with transaction.atomic():
            ok = apply_dodo_subscription_payload(
                self._payload(
                    status='on_hold',
                    next_billing_date=now + timedelta(days=30),
                )
            )
        self.assertTrue(ok)
        sub = Subscription.objects.get(user=self.user)
        self.assertEqual(sub.status, Subscription.Status.PAST_DUE)
        self.assertIsNotNone(sub.subscription_past_due_notified_for_period_end)
        mock_dispatch.assert_called()
        self.assertTrue(
            InAppNotification.objects.filter(user=self.user, title='Payment failed').exists()
        )

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


class InferBillingIntervalTests(TestCase):
    def test_monthly_from_period_length(self):
        now = timezone.now()
        sub = Subscription(
            user=User.objects.create_user(
                email='int@test.com',
                username='inttest',
                password='x',
            ),
            status=Subscription.Status.ACTIVE,
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
        )
        self.assertEqual(infer_billing_interval_from_subscription_period(sub), 'monthly')

    def test_yearly_from_period_length(self):
        now = timezone.now()
        sub = Subscription(
            user=User.objects.create_user(
                email='int2@test.com',
                username='inttest2',
                password='x',
            ),
            status=Subscription.Status.ACTIVE,
            current_period_start=now,
            current_period_end=now + timedelta(days=365),
        )
        self.assertEqual(infer_billing_interval_from_subscription_period(sub), 'yearly')

    def test_missing_period_returns_none(self):
        sub = Subscription(
            user=User.objects.create_user(
                email='int3@test.com',
                username='inttest3',
                password='x',
            ),
            status=Subscription.Status.ACTIVE,
        )
        self.assertIsNone(infer_billing_interval_from_subscription_period(sub))


@override_settings(BILLING_GRACE_DAYS=3)
class SubscriptionExpiryEntitlementsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='trialcx@test.com',
            username='trialcx',
            password='test-pass-123',
        )

    def test_canceled_after_trial_no_period_counts_as_expired(self):
        past = timezone.now() - timedelta(days=1)
        sub = Subscription.objects.create(
            user=self.user,
            status=Subscription.Status.CANCELED,
            trial_ends_at=past,
        )
        self.assertTrue(subscription_is_expired(sub))
        self.assertEqual(effective_subscription_expiry_at(sub), past)

    def test_canceled_paid_until_period_end_not_expired(self):
        future = timezone.now() + timedelta(days=10)
        sub = Subscription.objects.create(
            user=self.user,
            status=Subscription.Status.CANCELED,
            current_period_end=future,
            trial_ends_at=timezone.now() - timedelta(days=30),
        )
        self.assertFalse(subscription_is_expired(sub))


class BillingGatewayFactoryTests(TestCase):
    @override_settings(DODO_PAYMENTS_API_KEY='', BILLING_GATEWAY='dodo')
    def test_dodo_requires_api_key(self):
        with self.assertRaises(BillingConfigurationError):
            get_billing_gateway()

    @override_settings(BILLING_GATEWAY='not_a_real_gateway')
    def test_unknown_gateway_raises(self):
        with self.assertRaises(BillingConfigurationError):
            get_billing_gateway()


@override_settings(DEFAULT_AGENT_OPERATIONS_PER_MONTH=10)
class AgentUsageQuotaTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='quota@test.com',
            username='quotatest',
            password='test-pass-123',
        )
        self.plan = Plan.objects.create(
            name='Quota Test Plan',
            slug='quota-test-plan',
            max_teams=5,
            max_members=10,
            max_agent_operations_per_month=3,
            price_monthly=Decimal('10.00'),
            price_yearly=Decimal('100.00'),
        )
        Subscription.objects.create(
            user=self.user,
            plan=self.plan,
            status=Subscription.Status.ACTIVE,
        )

    def test_effective_limit_from_plan(self):
        self.assertEqual(get_effective_agent_ops_limit(self.user), 3)

    def test_consume_and_block_at_limit(self):
        self.assertTrue(try_consume_agent_operation(self.user).allowed)
        self.assertTrue(try_consume_agent_operation(self.user).allowed)
        self.assertTrue(try_consume_agent_operation(self.user).allowed)
        fourth = try_consume_agent_operation(self.user)
        self.assertFalse(fourth.allowed)
        self.assertEqual(fourth.used, 3)

    def test_refund_allows_another_operation(self):
        try_consume_agent_operation(self.user)
        try_consume_agent_operation(self.user)
        try_consume_agent_operation(self.user)
        self.assertFalse(try_consume_agent_operation(self.user).allowed)
        refund_agent_operation(self.user)
        self.assertTrue(try_consume_agent_operation(self.user).allowed)

    def test_unlimited_plan_skips_counter_rows(self):
        self.plan.max_agent_operations_per_month = None
        self.plan.save(update_fields=['max_agent_operations_per_month'])
        self.assertIsNone(get_effective_agent_ops_limit(self.user))
        self.assertTrue(try_consume_agent_operation(self.user).allowed)
        self.assertEqual(AgentUsageMonthly.objects.filter(user=self.user).count(), 0)


@override_settings(
    DODO_PAYMENTS_API_KEY='test_dummy_key_for_unit_tests',
    DODO_PAYMENTS_ENVIRONMENT='test_mode',
)
class BillingChangePlanViewTests(APITestCase):
    """POST /api/billing/change-plan/ with mocked Dodo client (no real HTTP)."""

    def setUp(self):
        self.user = User.objects.create_user(
            email='changeplan@test.com',
            username='changeplantest',
            password='test-pass-123',
        )
        self.client.force_authenticate(self.user)
        self.pro = Plan.objects.create(
            name='ChangePlan Pro U',
            slug='changeplan-pro-u',
            max_teams=10,
            max_members=20,
            price_monthly=Decimal('50.00'),
            price_yearly=Decimal('500.00'),
        )
        self.starter = Plan.objects.create(
            name='ChangePlan Starter U',
            slug='changeplan-starter-u',
            max_teams=2,
            max_members=5,
            price_monthly=Decimal('10.00'),
            price_yearly=Decimal('100.00'),
        )
        for plan, ext in (
            (self.pro, 'ext_prod_pro_m_u'),
            (self.starter, 'ext_prod_starter_m_u'),
        ):
            PlanGatewayProduct.objects.create(
                plan=plan,
                gateway=PlanGatewayProduct.Gateway.DODO,
                interval=PlanGatewayProduct.Interval.MONTHLY,
                external_product_id=ext,
            )

    def _subscription(self, *, plan: Plan):
        now = timezone.now()
        Subscription.objects.create(
            user=self.user,
            plan=plan,
            status=Subscription.Status.ACTIVE,
            gateway='dodo',
            gateway_subscription_id='sub_dodo_unit_test',
            gateway_customer_id='cus_unit_test',
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
        )

    @patch('base.billing_views.refresh_gateway_subscription_id_from_dodo', return_value=False)
    @patch('base.billing_views.get_billing_gateway')
    def test_upgrade_passes_subscription_id_positionally(self, mock_gw, _refresh):
        self._subscription(plan=self.starter)
        mock_client = MagicMock()
        mock_client.subscriptions.retrieve.return_value = SimpleNamespace(product_id='ext_prod_starter_m_u')
        mock_gw.return_value = MagicMock(code='dodo', client=mock_client)

        resp = self.client.post(
            '/api/billing/change-plan/',
            {'plan': str(self.pro.id), 'billing_interval': 'monthly'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200, getattr(resp, 'data', resp.content))
        mock_client.products.retrieve.assert_called_once_with(id='ext_prod_pro_m_u')
        args, kwargs = mock_client.subscriptions.change_plan.call_args
        self.assertEqual(args[0], 'sub_dodo_unit_test')
        self.assertEqual(kwargs.get('product_id'), 'ext_prod_pro_m_u')
        self.assertNotIn('effective_at', kwargs)
        sub = Subscription.objects.get(user=self.user)
        self.assertEqual(sub.plan_id, self.pro.id)

    @patch('base.billing_views.refresh_gateway_subscription_id_from_dodo', return_value=False)
    @patch('base.billing_views.get_billing_gateway')
    def test_downgrade_uses_next_billing_date_and_keeps_local_plan(self, mock_gw, _refresh):
        self._subscription(plan=self.pro)
        mock_client = MagicMock()
        mock_client.subscriptions.retrieve.return_value = SimpleNamespace(product_id='ext_prod_pro_m_u')
        mock_gw.return_value = MagicMock(code='dodo', client=mock_client)

        resp = self.client.post(
            '/api/billing/change-plan/',
            {'plan': str(self.starter.id), 'billing_interval': 'monthly'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200, getattr(resp, 'data', resp.content))
        self.assertTrue(resp.data.get('scheduled'))
        args, kwargs = mock_client.subscriptions.change_plan.call_args
        self.assertEqual(args[0], 'sub_dodo_unit_test')
        self.assertEqual(kwargs.get('effective_at'), 'next_billing_date')
        sub = Subscription.objects.get(user=self.user)
        self.assertEqual(sub.plan_id, self.pro.id)

    @patch('base.billing_views.refresh_gateway_subscription_id_from_dodo', return_value=False)
    @patch('base.billing_views.get_billing_gateway')
    def test_preflight_subscription_not_found_returns_recoverable_payload(self, mock_gw, _refresh):
        self._subscription(plan=self.starter)
        req = httpx.Request('GET', 'https://dodo.example/subscriptions/sub_x')
        resp404 = httpx.Response(404, request=req)
        nf = dodopayments.NotFoundError('gone', response=resp404, body={'message': 'not found'})
        mock_client = MagicMock()
        mock_client.subscriptions.retrieve.side_effect = nf
        mock_gw.return_value = MagicMock(code='dodo', client=mock_client)

        r = self.client.post(
            '/api/billing/change-plan/',
            {'plan': str(self.pro.id), 'billing_interval': 'monthly'},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(r.data.get('billing_error'), 'subscription_not_found')
        self.assertEqual(r.data.get('recovery'), 'checkout')
        self.assertIn("couldn't link", r.data.get('detail', '').lower())
        mock_client.subscriptions.change_plan.assert_not_called()


@override_settings(DODO_PAYMENTS_API_KEY='')
class StaffGrantSubscriptionTests(APITestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            email='staff@test.com',
            username='stafftest',
            password='pw',
            is_staff=True,
        )
        self.user = User.objects.create_user(
            email='grantee@test.com',
            username='grantee',
            password='pw',
        )
        self.plan = Plan.objects.create(
            name='Grant Pro',
            slug='grant-pro',
            max_teams=20,
            max_members=50,
            price_monthly=Decimal('49.00'),
            price_yearly=Decimal('490.00'),
            is_trial=False,
        )

    def test_non_staff_forbidden(self):
        self.client.force_authenticate(self.user)
        r = self.client.post(
            '/api/billing/staff/grant-subscription/',
            {'user_id': str(self.user.id), 'plan_id': str(self.plan.id)},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_staff_grants_paid_plan_and_logs(self):
        self.client.force_authenticate(self.staff)
        with patch('base.billing.subscription_notifications.dispatch_send_email_with_template') as mock_mail:
            r = self.client.post(
                '/api/billing/staff/grant-subscription/',
                {
                    'user_id': str(self.user.id),
                    'plan_id': str(self.plan.id),
                    'months_valid': 3,
                    'clear_gateway': True,
                    'note': 'Pilot access',
                },
                format='json',
            )
        self.assertEqual(r.status_code, status.HTTP_200_OK, getattr(r, 'data', r.content))
        sub = Subscription.objects.get(user=self.user)
        self.assertEqual(sub.plan_id, self.plan.id)
        self.assertEqual(sub.status, Subscription.Status.ACTIVE)
        self.assertFalse((sub.gateway_subscription_id or '').strip())
        self.assertIsNotNone(sub.current_period_end)
        self.assertEqual(SubscriptionGrantLog.objects.filter(recipient=self.user).count(), 1)
        self.assertTrue(
            InAppNotification.objects.filter(user=self.user, link='/billing').exists()
        )
        mock_mail.assert_called_once()
        self.assertEqual(mock_mail.call_args[0][3], [self.user.email])


@override_settings(
    DEFAULT_FROM_EMAIL='billing@test.resolvemeq.net',
    FRONTEND_URL='https://app.test',
    APP_NAME='ResolveMeQ Test',
)
class SubscriptionBillingNotificationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='billing-notify@test.com',
            username='billingnotify',
            password='pw',
        )
        self.plan = Plan.objects.create(
            name='Pro Notify Test',
            slug='pro-notify-test',
            max_teams=10,
            max_members=20,
            price_monthly=Decimal('29.00'),
            price_yearly=Decimal('290.00'),
        )

    def _sub(self, **kwargs):
        defaults = {
            'user': self.user,
            'plan': self.plan,
            'status': Subscription.Status.ACTIVE,
            'gateway': 'dodo',
            'gateway_subscription_id': 'sub_gw_1',
            'current_period_start': timezone.now(),
            'current_period_end': timezone.now() + timedelta(days=30),
        }
        defaults.update(kwargs)
        return Subscription.objects.create(**defaults)

    @patch('base.billing.subscription_notifications.dispatch_send_email_with_template')
    def test_welcome_on_first_gateway_link(self, mock_dispatch):
        sub = self._sub(gateway_subscription_id='')
        from base.billing.subscription_notifications import (
            handle_subscription_sync_notifications,
            snapshot_subscription,
        )

        before_snap = snapshot_subscription(sub)
        sub.gateway_subscription_id = 'sub_gw_new'
        sub.save()
        handle_subscription_sync_notifications(sub, before=before_snap)
        sub.refresh_from_db()
        self.assertIsNotNone(sub.subscription_welcome_notified_at)
        mock_dispatch.assert_called()
        self.assertTrue(
            InAppNotification.objects.filter(
                user=self.user, title='Subscription confirmed'
            ).exists()
        )

    @patch('base.billing.subscription_notifications.dispatch_send_email_with_template')
    def test_renewal_when_period_extends(self, mock_dispatch):
        now = timezone.now()
        sub = self._sub(
            subscription_welcome_notified_at=now,
            current_period_end=now + timedelta(days=10),
        )
        from base.billing.subscription_notifications import (
            handle_subscription_sync_notifications,
            snapshot_subscription,
        )

        before = snapshot_subscription(sub)
        sub.current_period_end = now + timedelta(days=40)
        sub.save()
        handle_subscription_sync_notifications(sub, before=before)
        sub.refresh_from_db()
        self.assertEqual(sub.subscription_renewed_notified_period_end, sub.current_period_end)
        mock_dispatch.assert_called()

    @patch('base.billing.subscription_notifications.dispatch_send_email_with_template')
    def test_expiring_soon_respects_dedup(self, mock_dispatch):
        ends = timezone.now() + timedelta(days=3)
        sub = self._sub(
            status=Subscription.Status.ACTIVE,
            current_period_end=ends,
        )
        from base.billing.subscription_notifications import notify_subscription_expiring_soon

        self.assertTrue(notify_subscription_expiring_soon(sub, ends_at=ends, days_remaining=3))
        mock_dispatch.reset_mock()
        self.assertFalse(notify_subscription_expiring_soon(sub, ends_at=ends, days_remaining=3))
        mock_dispatch.assert_not_called()

    @patch('base.billing.subscription_notifications.dispatch_send_email_with_template')
    def test_expired_respects_email_pref(self, mock_dispatch):
        from base.models import UserPreferences
        from base.billing.subscription_notifications import notify_subscription_expired

        sub = self._sub(
            status=Subscription.Status.CANCELED,
            current_period_end=timezone.now() - timedelta(days=5),
        )
        prefs, _ = UserPreferences.objects.get_or_create(user=self.user)
        prefs.email_notifications = False
        prefs.save()
        self.assertTrue(notify_subscription_expired(sub, expiry_detail='Your billing period has ended.'))
        mock_dispatch.assert_not_called()
        self.assertTrue(
            InAppNotification.objects.filter(user=self.user, title='Subscription no longer active').exists()
        )

    @patch('base.billing.subscription_notifications.dispatch_send_email_with_template')
    def test_trial_started_email_and_in_app(self, mock_dispatch):
        trial_plan = Plan.objects.create(
            name='Trial Notify',
            slug='trial-notify-test',
            is_trial=True,
            max_teams=3,
            max_members=5,
        )
        sub = Subscription.objects.create(
            user=self.user,
            plan=trial_plan,
            status=Subscription.Status.TRIAL,
            trial_ends_at=timezone.now() + timedelta(days=14),
        )
        from base.billing.subscription_notifications import maybe_notify_trial_started

        self.assertTrue(maybe_notify_trial_started(sub))
        sub.refresh_from_db()
        self.assertIsNotNone(sub.subscription_trial_started_notified_at)
        mock_dispatch.assert_called()
        self.assertTrue(
            InAppNotification.objects.filter(user=self.user, title='Free trial started').exists()
        )

    @patch('base.billing.subscription_notifications.dispatch_send_email_with_template')
    def test_trial_started_dedup(self, mock_dispatch):
        trial_plan = Plan.objects.create(
            name='Trial Dedup',
            slug='trial-dedup-test',
            is_trial=True,
            max_teams=3,
            max_members=5,
        )
        sub = Subscription.objects.create(
            user=self.user,
            plan=trial_plan,
            status=Subscription.Status.TRIAL,
            trial_ends_at=timezone.now() + timedelta(days=14),
            subscription_trial_started_notified_at=timezone.now(),
        )
        from base.billing.subscription_notifications import maybe_notify_trial_started

        self.assertFalse(maybe_notify_trial_started(sub))
        mock_dispatch.assert_not_called()

    @patch('base.billing.subscription_notifications.dispatch_send_email_with_template')
    def test_past_due_on_status_transition(self, mock_dispatch):
        now = timezone.now()
        sub = self._sub(
            subscription_welcome_notified_at=now,
            current_period_end=now + timedelta(days=30),
        )
        from base.billing.subscription_notifications import (
            handle_subscription_sync_notifications,
            snapshot_subscription,
        )

        before = snapshot_subscription(sub)
        sub.status = Subscription.Status.PAST_DUE
        sub.save(update_fields=['status', 'updated_at'])
        handle_subscription_sync_notifications(sub, before=before)
        sub.refresh_from_db()
        self.assertEqual(sub.subscription_past_due_notified_for_period_end, sub.current_period_end)
        mock_dispatch.assert_called()
        self.assertTrue(
            InAppNotification.objects.filter(user=self.user, title='Payment failed').exists()
        )

    @patch('base.billing.subscription_notifications.dispatch_send_email_with_template')
    def test_past_due_dedup_same_period(self, mock_dispatch):
        now = timezone.now()
        period_end = now + timedelta(days=30)
        sub = self._sub(
            status=Subscription.Status.PAST_DUE,
            subscription_welcome_notified_at=now,
            current_period_end=period_end,
            subscription_past_due_notified_for_period_end=period_end,
        )
        from base.billing.subscription_notifications import notify_subscription_past_due

        self.assertFalse(notify_subscription_past_due(sub))
        mock_dispatch.assert_not_called()
