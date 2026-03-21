"""
Billing and subscription API views.
"""
import logging

from django.conf import settings as django_settings
from rest_framework import permissions, status
from rest_framework.generics import GenericAPIView, ListAPIView
from rest_framework.response import Response

from base.billing.exceptions import BillingConfigurationError
from base.billing.gateways.factory import get_billing_gateway
from base.models import Plan, Subscription, Invoice, Team, PlanGatewayProduct
from base.serializers import (
    PlanSerializer,
    SubscriptionSerializer,
    InvoiceSerializer,
    BillingCheckoutSessionSerializer,
)

logger = logging.getLogger(__name__)

try:
    import dodopayments
except ImportError:
    dodopayments = None


def get_max_teams_for_user(user):
    """Return max teams allowed for this user (from subscription or settings)."""
    try:
        sub = Subscription.objects.get(user=user)
        if sub.plan_id:
            return sub.plan.max_teams
        return getattr(django_settings, 'PLAN_MAX_TEAMS', 20)
    except Subscription.DoesNotExist:
        return getattr(django_settings, 'PLAN_MAX_TEAMS', 20)


def get_plan_for_user(user):
    """Return the plan for this user's subscription, or None."""
    try:
        sub = Subscription.objects.get(user=user)
        return sub.plan
    except Subscription.DoesNotExist:
        return None


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
        sub, _ = Subscription.objects.get_or_create(
            user=request.user,
            defaults={'status': Subscription.Status.ACTIVE},
        )
        serializer = self.get_serializer(sub)
        return Response(serializer.data)

    def patch(self, request):
        """Update subscription (e.g. change plan). Body: { "plan": "<plan_uuid>" }."""
        sub = Subscription.objects.filter(user=request.user).first()
        if not sub:
            sub, _ = Subscription.objects.get_or_create(
                user=request.user,
                defaults={'status': Subscription.Status.ACTIVE},
            )
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

    def get(self, request):
        teams_count = Team.objects.filter(owner=request.user).count()
        max_teams = get_max_teams_for_user(request.user)
        return Response({
            'teams_used': teams_count,
            'teams_limit': max_teams,
            'can_create_team': teams_count < max_teams,
        })


class InvoiceListView(ListAPIView):
    """List invoices for current user's subscription."""
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = InvoiceSerializer

    def get_queryset(self):
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

        try:
            result = gateway.create_checkout_session(
                product_id=mapping.external_product_id,
                customer_email=email,
                return_url=return_url,
                customer_name=customer_name,
                metadata=metadata,
            )
        except dodopayments.APIStatusError:
            logger.exception('Dodo checkout_sessions.create failed')
            return Response(
                {'detail': 'Unable to start checkout. Please try again later.'},
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
