"""
Billing and subscription API views.
"""
import logging
import os

from django.conf import settings as django_settings
from rest_framework import permissions, serializers, status
from rest_framework.generics import GenericAPIView, ListAPIView
from rest_framework.response import Response

from base.billing.exceptions import BillingConfigurationError
from base.billing.gateways.factory import get_billing_gateway
from base.billing.payment_sync import sync_invoices_from_dodo
from base.billing.subscription_sync import apply_dodo_subscription_payload
from base.agent_usage import get_agent_usage_snapshot
from base.models import Plan, Subscription, Invoice, Team, PlanGatewayProduct, SupportContactSubmission
from base.serializers import (
    PlanSerializer,
    SubscriptionSerializer,
    InvoiceSerializer,
    BillingCheckoutSessionSerializer,
    BillingChangePlanSerializer,
    PortalSupportContactSerializer,
)
from base.tasks import dispatch_send_email_with_template

logger = logging.getLogger(__name__)

try:
    import dodopayments
except ImportError:
    dodopayments = None


def get_max_teams_for_user(user):
    """Return max teams allowed for this user (from subscription or settings)."""
    try:
        sub = Subscription.objects.select_related('plan').get(user=user)
    except Subscription.DoesNotExist:
        sub = None
    from base.billing.entitlements import get_entitlements_for_subscription, reconcile_subscription_status
    reconcile_subscription_status(sub)
    ent = get_entitlements_for_subscription(sub)
    return int(ent.max_teams)


def get_plan_for_user(user):
    """Return the plan for this user's subscription, or None."""
    try:
        sub = Subscription.objects.select_related('plan').get(user=user)
    except Subscription.DoesNotExist:
        sub = None
    from base.billing.entitlements import get_entitlements_for_subscription, reconcile_subscription_status
    reconcile_subscription_status(sub)
    ent = get_entitlements_for_subscription(sub)
    # When expired, treat as no paid plan for feature gating.
    return sub.plan if (sub and not ent.is_expired) else None


def get_max_members_for_user(user) -> int:
    """Return max team members allowed for this user (from active subscription or expired caps)."""
    try:
        sub = Subscription.objects.select_related('plan').get(user=user)
    except Subscription.DoesNotExist:
        sub = None
    from base.billing.entitlements import get_entitlements_for_subscription, reconcile_subscription_status
    reconcile_subscription_status(sub)
    ent = get_entitlements_for_subscription(sub)
    return int(ent.max_members_per_team)


class PlanListView(ListAPIView):
    """List available plans."""
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = PlanSerializer
    queryset = Plan.objects.filter(is_active=True)


class CurrentSubscriptionView(GenericAPIView):
    """Get, create, or update current user's subscription."""
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = SubscriptionSerializer

    def get(self, request):
        sub, created = Subscription.objects.get_or_create(
            user=request.user,
            defaults={'status': Subscription.Status.ACTIVE},
        )
        if created:
            trial_plan = Plan.objects.filter(slug='trial', is_active=True).first()
            if trial_plan:
                from django.utils import timezone
                from datetime import timedelta
                sub.plan = trial_plan
                sub.status = Subscription.Status.TRIAL
                sub.trial_ends_at = timezone.now() + timedelta(days=14)
                sub.save(update_fields=['plan', 'status', 'trial_ends_at', 'updated_at'])
        # Best-effort: sync subscription period/status from gateway on read.
        # This prevents stale `current_period_end` when webhooks are delayed/missed.
        try:
            gateway = get_billing_gateway()
            if getattr(gateway, "code", None) == "dodo" and (sub.gateway_subscription_id or "").strip():
                client = getattr(gateway, "client", None)
                if client and hasattr(client, "subscriptions"):
                    remote = client.subscriptions.retrieve(subscription_id=sub.gateway_subscription_id)
                    payload = getattr(remote, "data", None) or remote
                    if payload:
                        apply_dodo_subscription_payload(payload)
                        sub = Subscription.objects.filter(user=request.user).first() or sub
        except Exception as exc:
            logger.debug("Subscription sync skipped: %s", exc)
        serializer = self.get_serializer(sub)
        return Response(serializer.data)

    def patch(self, request):
        """Update subscription (e.g. change plan). Body: { "plan": "<plan_uuid>" }."""
        sub = Subscription.objects.filter(user=request.user).first()
        if not sub:
            sub, created = Subscription.objects.get_or_create(
                user=request.user,
                defaults={'status': Subscription.Status.ACTIVE},
            )
        if created:
            trial_plan = Plan.objects.filter(slug='trial', is_active=True).first()
            if trial_plan:
                from django.utils import timezone
                from datetime import timedelta
                sub.plan = trial_plan
                sub.status = Subscription.Status.TRIAL
                sub.trial_ends_at = timezone.now() + timedelta(days=14)
                sub.save(update_fields=['plan', 'status', 'trial_ends_at', 'updated_at'])
        plan_id = request.data.get('plan')
        if plan_id is not None:
            plan = Plan.objects.filter(id=plan_id, is_active=True).first()
            if not plan:
                return Response(
                    {'error': 'Invalid or inactive plan.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            sub.plan = plan
            from django.utils import timezone
            now = timezone.now()
            if not sub.current_period_end or sub.current_period_end <= now:
                from dateutil.relativedelta import relativedelta
                sub.current_period_start = now
                sub.current_period_end = now + relativedelta(months=1)
            sub.save(update_fields=['plan', 'current_period_start', 'current_period_end', 'updated_at'])
        serializer = self.get_serializer(sub)
        return Response(serializer.data)


class BillingUsageView(GenericAPIView):
    """Return usage stats for billing (teams owned by current user count)."""
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = serializers.Serializer

    def get_queryset(self):
        return Team.objects.none()

    def get(self, request):
        teams_count = Team.objects.filter(owner=request.user).count()
        max_teams = get_max_teams_for_user(request.user)
        payload = {
            'teams_used': teams_count,
            'teams_limit': max_teams,
            'can_create_team': teams_count < max_teams,
        }
        payload.update(get_agent_usage_snapshot(request.user))
        return Response(payload)


class InvoiceListView(ListAPIView):
    """
    List transactions for the current user (Billing Transaction History).
    Fetches payments from Dodo directly; falls back to local invoices.
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = InvoiceSerializer

    def list(self, request, *args, **kwargs):
        # Always sync from Dodo first so we persist transactions for tracking
        sync_invoices_from_dodo(request.user)
        queryset = self.filter_queryset(
            Invoice.objects.filter(subscription__user=request.user).select_related('subscription')
        )
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Invoice.objects.none()
        return Invoice.objects.filter(
            subscription__user=self.request.user
        ).select_related('subscription')


class BillingCheckoutSessionView(GenericAPIView):
    """
    Start a hosted checkout for a subscription plan (Dodo product_cart flow).
    Requires PlanGatewayProduct rows — create them with: manage.py sync_dodo_plan_products
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = BillingCheckoutSessionSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        plan_id = serializer.validated_data['plan']
        interval = serializer.validated_data['billing_interval']
        return_url_in = serializer.validated_data.get('return_url')

        plan = Plan.objects.filter(id=plan_id, is_active=True).first()
        if not plan:
            return Response(
                {'detail': 'Invalid or inactive plan.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            gateway = get_billing_gateway()
        except BillingConfigurationError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        mapping = PlanGatewayProduct.objects.filter(
            plan=plan,
            gateway=gateway.code,
            interval=interval,
        ).first()
        if not mapping:
            return Response(
                {
                    'detail': (
                        'This plan is not provisioned on the payment provider for the '
                        'selected billing interval. Run: python manage.py sync_dodo_plan_products'
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if return_url_in:
            return_url = return_url_in
        else:
            default_return = getattr(django_settings, 'BILLING_CHECKOUT_RETURN_URL', '').strip()
            if default_return:
                return_url = default_return
            else:
                fe = getattr(django_settings, 'FRONTEND_URL', 'http://localhost:5173').rstrip('/')
                return_url = f'{fe}/billing/complete'

        email = getattr(request.user, 'email', None) or ''
        if not email:
            return Response(
                {'detail': 'Your account has no email; cannot start checkout.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        metadata = {
            'resolvemeq_user_id': str(request.user.id),
            'resolvemeq_plan_id': str(plan.id),
            'billing_interval': interval,
        }

        u = request.user
        name_parts = [getattr(u, 'first_name', None) or '', getattr(u, 'last_name', None) or '']
        customer_name = ' '.join(p.strip() for p in name_parts if p and str(p).strip()) or None

        if dodopayments is None:
            return Response(
                {'detail': 'Payment provider SDK is not installed (dodopayments).'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        def _dodo_error_detail(exc: BaseException) -> str:
            body = getattr(exc, 'body', None)
            if isinstance(body, dict):
                return str(body.get('message') or body.get('code') or getattr(exc, 'message', '') or '')
            return str(getattr(exc, 'message', '') or '')

        try:
            result = gateway.create_checkout_session(
                product_id=mapping.external_product_id,
                customer_email=email,
                return_url=return_url,
                customer_name=customer_name,
                metadata=metadata,
            )
        except dodopayments.UnprocessableEntityError as exc:
            logger.warning('Dodo checkout_sessions.create rejected: %s', exc)
            detail = _dodo_error_detail(exc) or 'Invalid checkout request.'
            hint = (
                ' If the product no longer exists in Dodo, run: '
                'python manage.py sync_dodo_plan_products --recreate'
            )
            if 'does not exist' in detail.lower():
                detail = detail + hint
            return Response({'detail': detail}, status=status.HTTP_400_BAD_REQUEST)
        except dodopayments.APIStatusError as exc:
            logger.exception('Dodo checkout_sessions.create failed')
            return Response(
                {
                    'detail': _dodo_error_detail(exc)
                    or 'Unable to start checkout. Please try again later.',
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except dodopayments.APIConnectionError:
            logger.exception('Dodo API connection error during checkout')
            return Response(
                {'detail': 'Payment provider unreachable. Please try again later.'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        if not result.checkout_url:
            return Response(
                {'detail': 'Checkout URL was not returned by the payment provider.'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response(
            {
                'checkout_url': result.checkout_url,
                'session_id': result.session_id,
            },
            status=status.HTTP_200_OK,
        )


class BillingChangePlanView(GenericAPIView):
    """
    Change plan for existing Dodo subscribers. Uses Dodo change-plan API.
    For users without a Dodo subscription, use checkout instead.
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = BillingChangePlanSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        plan_id = serializer.validated_data['plan']
        interval = serializer.validated_data['billing_interval']

        sub = Subscription.objects.filter(user=request.user).first()
        if not sub or not (sub.gateway_subscription_id or '').strip():
            return Response(
                {'detail': 'No active Dodo subscription. Use checkout to subscribe.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        plan = Plan.objects.filter(id=plan_id, is_active=True).first()
        if not plan:
            return Response({'detail': 'Invalid or inactive plan.'}, status=status.HTTP_400_BAD_REQUEST)

        mapping = PlanGatewayProduct.objects.filter(
            plan=plan,
            gateway=PlanGatewayProduct.Gateway.DODO,
            interval=interval,
        ).first()
        if not mapping:
            return Response(
                {'detail': 'Plan not provisioned for this interval. Run sync_dodo_plan_products.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            gateway = get_billing_gateway()
        except BillingConfigurationError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        if getattr(gateway, 'code', None) != 'dodo':
            return Response({'detail': 'Plan changes only supported for Dodo.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            gateway.client.subscriptions.change_plan(
                subscription_id=sub.gateway_subscription_id,
                product_id=mapping.external_product_id,
                proration_billing_mode='difference_immediately',
                quantity=1,
            )
        except Exception as exc:
            if dodopayments and isinstance(exc, dodopayments.APIStatusError):
                body = getattr(exc, 'body', None) or {}
                detail = body.get('message') or body.get('code') or str(exc)
            else:
                detail = str(exc)
            logger.exception('Dodo change_plan failed')
            return Response({'detail': detail or 'Plan change failed.'}, status=status.HTTP_400_BAD_REQUEST)

        sub.plan = plan
        sub.save(update_fields=['plan', 'updated_at'])
        logger.info('Plan changed to %s for user %s', plan.slug, request.user.id)
        return Response({'detail': 'Plan updated successfully.'})


class BillingCustomerPortalView(GenericAPIView):
    """
    Create a Dodo customer portal session and return the URL.
    Lets users update payment methods, view invoices, etc.
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = serializers.Serializer

    def get_queryset(self):
        return Team.objects.none()

    def post(self, request):
        sub = Subscription.objects.filter(user=request.user).first()
        customer_id = (sub.gateway_customer_id or '').strip() if sub else ''
        if not customer_id:
            return Response(
                {'detail': 'No billing account linked. Subscribe first to manage payment methods.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            gateway = get_billing_gateway()
        except BillingConfigurationError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        if getattr(gateway, 'code', None) != 'dodo':
            return Response({'detail': 'Customer portal only available for Dodo.'}, status=status.HTTP_400_BAD_REQUEST)

        client = getattr(gateway, 'client', None)
        if not client or not hasattr(client, 'customers'):
            return Response({'detail': 'Billing provider not configured.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        try:
            session = client.customers.customer_portal.create(customer_id=customer_id)
            url = getattr(session, 'link', None) or ''
            if not url:
                return Response({'detail': 'No portal URL returned.'}, status=status.HTTP_502_BAD_GATEWAY)
            return Response({'url': url})
        except Exception as exc:
            logger.exception('Dodo customer portal create failed')
            detail = str(exc)
            if dodopayments and isinstance(exc, dodopayments.APIStatusError):
                body = getattr(exc, 'body', None) or {}
                detail = body.get('message') or body.get('detail') or detail
            return Response({'detail': detail or 'Failed to open billing portal.'}, status=status.HTTP_400_BAD_REQUEST)


def _support_contact_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def _support_contact_notify_recipients():
    raw = os.getenv('SUPPORT_CONTACT_NOTIFY_EMAILS', '').strip()
    if raw:
        return [e.strip() for e in raw.split(',') if e.strip()]
    single = (getattr(django_settings, 'SUPPORT_EMAIL', None) or '').strip()
    return [single] if single else []


def _email_admins_support_submission(submission):
    recipients = _support_contact_notify_recipients()
    if not recipients:
        logger.warning(
            'Support contact submission %s saved but no notify emails configured '
            '(set SUPPORT_CONTACT_NOTIFY_EMAILS or SUPPORT_EMAIL).',
            submission.id,
        )
        return
    app_name = getattr(django_settings, 'APP_NAME', 'ResolveMeQ')
    subj = (submission.subject or '').strip() or 'Billing / account help'
    data = {
        'subject': f'[{app_name}] Support: {subj} — {submission.email}',
    }
    uname = ''
    if submission.user_id and submission.user:
        uname = (submission.user.get_full_name() or '').strip() or submission.user.email
    context = {
        'app_name': app_name,
        'submitter_email': submission.email,
        'submitter_name': uname or submission.email,
        'user_id': str(submission.user_id) if submission.user_id else '—',
        'subject_line': subj,
        'message': submission.message,
        'page_context': submission.page_context or 'billing',
        'created_at': submission.created_at.isoformat() if submission.created_at else '',
        'ip_address': submission.ip_address or '—',
    }
    try:
        dispatch_send_email_with_template(
            data,
            'support_contact_admin.html',
            context,
            recipients,
        )
    except Exception as exc:
        logger.exception('Failed to send support contact admin email: %s', exc)


class BillingSupportContactView(GenericAPIView):
    """
    Logged-in user submits a support message from the portal (Billing page).
    Persists SupportContactSubmission and emails configured admin addresses.
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = PortalSupportContactSerializer

    def get_queryset(self):
        return SupportContactSubmission.objects.none()

    def post(self, request):
        ser = PortalSupportContactSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
        subj = (ser.validated_data.get('subject') or '').strip()
        page = (ser.validated_data.get('page_context') or 'billing').strip()[:64] or 'billing'
        submission = SupportContactSubmission.objects.create(
            user=request.user,
            email=(request.user.email or '').strip() or 'unknown@invalid',
            subject=subj[:200],
            message=ser.validated_data['message'],
            page_context=page,
            ip_address=_support_contact_client_ip(request),
        )
        _email_admins_support_submission(submission)
        return Response(
            {
                'ok': True,
                'message': 'Thanks — we received your message and will get back to you soon.',
                'id': str(submission.id),
            },
            status=status.HTTP_201_CREATED,
        )
