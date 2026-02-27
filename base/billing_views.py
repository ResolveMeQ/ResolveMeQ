"""
Billing and subscription API views.
"""
from django.conf import settings as django_settings
from rest_framework import permissions, status
from rest_framework.generics import GenericAPIView, ListAPIView
from rest_framework.response import Response

from base.models import Plan, Subscription, Invoice, Team
from base.serializers import PlanSerializer, SubscriptionSerializer, InvoiceSerializer


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
