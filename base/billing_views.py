"""
Billing and subscription API views.
"""
import logging
import os

from django.conf import settings as django_settings
from django.utils import timezone
from rest_framework import permissions, serializers, status
from rest_framework.generics import GenericAPIView, ListAPIView
from rest_framework.response import Response

from base.billing.exceptions import BillingConfigurationError
from base.billing.gateways.factory import get_billing_gateway
from base.billing.entitlements import infer_billing_interval_from_subscription_period
from base.billing.payment_sync import refresh_gateway_subscription_id_from_dodo, sync_invoices_from_dodo
from base.billing.staff_grant import apply_staff_subscription_grant
from base.billing.services import plan_price_for_interval
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
    StaffGrantSubscriptionSerializer,
)
from base.tasks import dispatch_send_email_with_template

logger = logging.getLogger(__name__)

try:
    import dodopayments
except ImportError:
    dodopayments = None


def _dodo_body_message_lower(exc: BaseException) -> str:
    """Best-effort string from Dodo error JSON for matching (message/detail/code)."""
    body = getattr(exc, 'body', None)
    if not isinstance(body, dict):
        return ''
    parts: list[str] = []
    for key in ('message', 'detail', 'code', 'error'):
        v = body.get(key)
        if v is None:
            continue
        if isinstance(v, str):
            parts.append(v)
        elif isinstance(v, list) and v:
            parts.append(str(v[0]))
        else:
            parts.append(str(v))
    return ' '.join(parts).lower()


def _dodo_is_not_found(exc: BaseException) -> bool:
    """True when Dodo indicates missing subscription or product (404 or same message body)."""
    if dodopayments and isinstance(exc, dodopayments.NotFoundError):
        return True
    if dodopayments and isinstance(exc, dodopayments.APIStatusError):
        if getattr(exc, 'status_code', None) == 404:
            return True
        msg = _dodo_body_message_lower(exc)
        if msg and (
            'could not be found' in msg
            or 'could not find' in msg
            or 'does not exist' in msg
            or 'not found' in msg
            or 'wrong id' in msg
            or ('environment' in msg and 'match' in msg)
        ):
            return True
    return False


def _dodo_change_plan_kwargs(sub, plan, mapping, interval: str) -> tuple:
    """
    Build kwargs for subscriptions.change_plan.
    Returns (kwargs, scheduled_downgrade) where scheduled_downgrade means effective_at=next_billing_date.
    """
    kwargs: dict = {
        'subscription_id': sub.gateway_subscription_id,
        'product_id': mapping.external_product_id,
        'proration_billing_mode': 'difference_immediately',
        'quantity': 1,
    }
    scheduled = False
    current = sub.plan
    if current and current.id != plan.id:
        try:
            old_p = plan_price_for_interval(current, interval)
            new_p = plan_price_for_interval(plan, interval)
            if new_p < old_p:
                kwargs['effective_at'] = 'next_billing_date'
                scheduled = True
        except ValueError:
            pass
    return kwargs, scheduled


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
                from base.billing.subscription_notifications import maybe_notify_trial_started

                maybe_notify_trial_started(sub)
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
        """
        Switch to a free/trial plan with no payment relationship (e.g. downgrading off a
        trial before ever subscribing). Body: { "plan": "<plan_uuid>" }.

        This is NOT the paid plan-change path -- paid upgrades/downgrades must go through
        BillingChangePlanView (existing Dodo subscription) or the checkout flow (new
        subscription), both of which actually talk to the payment gateway. This endpoint
        never has, so it must refuse to touch a Dodo-linked subscription or hand out a
        priced plan for free.
        """
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
                from base.billing.subscription_notifications import maybe_notify_trial_started

                maybe_notify_trial_started(sub)
        plan_id = request.data.get('plan')
        if plan_id is not None:
            if (sub.gateway_subscription_id or '').strip():
                return Response(
                    {
                        'error': 'has_active_subscription',
                        'detail': 'You have an active paid subscription. Use change-plan or checkout instead.',
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            plan = Plan.objects.filter(id=plan_id, is_active=True).first()
            if not plan:
                return Response(
                    {'error': 'Invalid or inactive plan.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if not plan.is_trial and plan.price_monthly > 0:
                return Response(
                    {
                        'error': 'paid_plan_requires_checkout',
                        'detail': 'This plan requires payment. Use checkout to subscribe.',
                    },
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

        inferred = infer_billing_interval_from_subscription_period(sub)
        if inferred and inferred != interval:
            logger.info(
                'change_plan: billing_interval %s -> %s (from current_period_start/end)',
                interval,
                inferred,
            )
            interval = inferred

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

        # Preflight: subscription id exists in this Dodo environment (TEST vs LIVE mismatch otherwise 404s).
        for pre in (1, 2):
            try:
                remote_sub = gateway.client.subscriptions.retrieve(
                    subscription_id=sub.gateway_subscription_id
                )
                logger.info(
                    'change_plan preflight ok: subscription_id=%s remote_product_id=%s',
                    (sub.gateway_subscription_id or '')[:16],
                    (getattr(remote_sub, 'product_id', None) or '')[:16],
                )
                break
            except Exception as exc:
                if pre == 1 and _dodo_is_not_found(exc) and refresh_gateway_subscription_id_from_dodo(
                    request.user, sub
                ):
                    sub.refresh_from_db()
                    logger.info('change_plan preflight: refreshed gateway_subscription_id, retrying retrieve')
                    continue
                if _dodo_is_not_found(exc):
                    # User‑friendly copy + machine‑readable recovery for the app (checkout fallback).
                    return Response(
                        {
                            'detail': (
                                "We couldn't link your account to your payment subscription "
                                '(often after switching billing modes or a refresh delay). '
                                'Continue below—your card details stay secure.'
                            ),
                            'billing_error': 'subscription_not_found',
                            'recovery': 'checkout',
                        },
                        status=status.HTTP_409_CONFLICT,
                    )
                logger.exception('Dodo subscription.retrieve preflight failed')
                return Response(
                    {'detail': 'Payment provider error while verifying subscription. Try again later.'},
                    status=status.HTTP_502_BAD_GATEWAY,
                )

        # Preflight: target product id exists (stale PlanGatewayProduct row vs dashboard).
        try:
            gateway.client.products.retrieve(id=mapping.external_product_id)
        except Exception as exc:
            if _dodo_is_not_found(exc):
                slug = (plan.slug or 'unknown').strip() or 'unknown'
                return Response(
                    {
                        'detail': (
                            f'Dodo has no product with id "{mapping.external_product_id}" '
                            f'(plan {slug}, {interval}). Re-create mappings: '
                            f'python manage.py sync_dodo_plan_products --plan-slug {slug} --recreate '
                            'Use the same DODO_PAYMENTS_ENVIRONMENT as this subscription.'
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            logger.exception('Dodo products.retrieve preflight failed')
            return Response(
                {'detail': 'Payment provider error while verifying target plan. Try again later.'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        change_kwargs, scheduled_downgrade = _dodo_change_plan_kwargs(sub, plan, mapping, interval)
        downgrade_fallback_immediate = False

        def _change_plan_error_response(exc) -> Response:
            if _dodo_is_not_found(exc):
                logger.warning('Dodo change_plan: subscription missing or wrong environment: %s', exc)
                return Response(
                    {
                        'detail': (
                            "We couldn't link your account to your payment subscription "
                            '(often after switching billing modes or a refresh delay). '
                            'Continue below—your card details stay secure.'
                        ),
                        'billing_error': 'subscription_not_found',
                        'recovery': 'checkout',
                    },
                    status=status.HTTP_409_CONFLICT,
                )
            if dodopayments and isinstance(exc, dodopayments.APIStatusError):
                body = getattr(exc, 'body', None) or {}
                detail = body.get('message') or body.get('code') or str(exc)
            else:
                detail = str(exc)
            logger.exception('Dodo change_plan failed')
            return Response(
                {'detail': detail or 'Plan change failed.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        def _run_change_plan_with_subscription_refresh(kw: dict) -> None:
            for attempt in (1, 2):
                try:
                    w = dict(kw)
                    sid = w.pop('subscription_id')
                    gateway.client.subscriptions.change_plan(sid, **w)
                    return
                except Exception as exc:
                    if attempt == 1 and _dodo_is_not_found(exc):
                        if refresh_gateway_subscription_id_from_dodo(request.user, sub):
                            sub.refresh_from_db()
                            kw['subscription_id'] = sub.gateway_subscription_id
                            change_kwargs['subscription_id'] = sub.gateway_subscription_id
                            logger.info('change_plan: retried after refreshing gateway_subscription_id')
                            continue
                    raise

        exc_out = None
        try:
            _run_change_plan_with_subscription_refresh(dict(change_kwargs))
        except Exception as exc_first:
            exc_out = exc_first
            if (
                change_kwargs.get('effective_at') == 'next_billing_date'
                and _dodo_is_not_found(exc_first)
            ):
                logger.warning(
                    'change_plan: effective_at=next_billing_date returned not-found; retrying without schedule: %s',
                    exc_first,
                )
                try:
                    kw_immediate = {k: v for k, v in change_kwargs.items() if k != 'effective_at'}
                    _run_change_plan_with_subscription_refresh(kw_immediate)
                    downgrade_fallback_immediate = True
                    exc_out = None
                except Exception as exc2:
                    exc_out = exc2

        if exc_out is not None:
            return _change_plan_error_response(exc_out)

        if scheduled_downgrade and not downgrade_fallback_immediate:
            logger.info(
                'Plan change scheduled (next_billing_date) to %s for user %s — local plan unchanged until webhook',
                plan.slug,
                request.user.id,
            )
            return Response(
                {
                    'detail': (
                        'Downgrade scheduled for your next billing date. '
                        'You keep your current plan until then; we will update your account when Dodo confirms.'
                    ),
                    'scheduled': True,
                }
            )

        sub.plan = plan
        sub.save(update_fields=['plan', 'updated_at'])
        logger.info('Plan changed to %s for user %s', plan.slug, request.user.id)
        return Response({'detail': 'Plan updated successfully.', 'scheduled': False})


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
            status=SupportContactSubmission.Status.OPEN,
        )
        _email_admins_support_submission(submission)
        ticket = None
        try:
            from tickets.support_enquiry import create_billing_support_ticket

            ticket = create_billing_support_ticket(
                request.user,
                subject=subj,
                message=ser.validated_data['message'],
                page_context=page,
                submission=submission,
            )
        except Exception as exc:
            logger.exception('Billing support ticket creation failed for submission %s: %s', submission.id, exc)
        if ticket:
            message = (
                f'Thanks — we opened ticket #{ticket.ticket_id} for your request. '
                'You will get updates in Tickets and by email when our team replies.'
            )
        else:
            message = 'Thanks — we received your message and will get back to you soon.'
        return Response(
            {
                'ok': True,
                'message': message,
                'id': str(submission.id),
                'ticket_id': ticket.ticket_id if ticket else None,
            },
            status=status.HTTP_201_CREATED,
        )


class StaffGrantSubscriptionView(GenericAPIView):
    """
    Staff-only: assign or extend a user's subscription outside self-serve checkout
    (complimentary access, pilots, manual sales). Writes ``Subscription`` and a
    ``SubscriptionGrantLog`` row for audit.

    Does not charge Dodo. If ``clear_gateway`` is true (default), gateway ids are
    cleared so the row is not confused with an active Dodo subscription; the user
    can still subscribe via checkout later.

    POST body: ``user_id``, ``plan_id``, optional ``months_valid`` (1–60, default 12),
    ``clear_gateway`` (default true), ``note`` (optional).
    """
    permission_classes = [permissions.IsAdminUser]
    serializer_class = StaffGrantSubscriptionSerializer

    def get_queryset(self):
        return Team.objects.none()

    def post(self, request):
        from django.contrib.auth import get_user_model

        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        User = get_user_model()
        user_id = ser.validated_data['user_id']
        plan_id = ser.validated_data['plan_id']
        months_valid = int(ser.validated_data['months_valid'])
        clear_gateway = bool(ser.validated_data['clear_gateway'])
        note = (ser.validated_data.get('note') or '').strip()

        recipient = User.objects.filter(id=user_id, is_active=True).first()
        if not recipient:
            return Response({'detail': 'User not found or inactive.'}, status=status.HTTP_404_NOT_FOUND)
        plan = Plan.objects.filter(id=plan_id, is_active=True).first()
        if not plan:
            return Response({'detail': 'Plan not found or inactive.'}, status=status.HTTP_400_BAD_REQUEST)

        sub = apply_staff_subscription_grant(
            recipient=recipient,
            plan=plan,
            months_valid=months_valid,
            clear_gateway=clear_gateway,
            note=note,
            granted_by=request.user,
        )
        out = SubscriptionSerializer(sub, context={'request': request}).data
        return Response({'detail': 'Subscription updated.', 'subscription': out}, status=status.HTTP_200_OK)
