from __future__ import annotations

from typing import TYPE_CHECKING

from django.conf import settings

from base.billing.exceptions import BillingConfigurationError
from base.billing.gateways.base import BillingGateway, CheckoutSessionResult

if TYPE_CHECKING:
    from base.models import Plan


class DodoGateway(BillingGateway):
    code = 'dodo'

    def __init__(self, *, bearer_token: str, environment: str):
        self._bearer_token = bearer_token
        self._environment = environment
        self._client = None

    @classmethod
    def from_settings(cls) -> DodoGateway:
        token = (getattr(settings, 'DODO_PAYMENTS_API_KEY', None) or '').strip()
        if not token:
            raise BillingConfigurationError(
                'DODO_PAYMENTS_API_KEY is not set. Add it to your environment.'
            )
        env = getattr(settings, 'DODO_PAYMENTS_ENVIRONMENT', 'test_mode')
        return cls(bearer_token=token, environment=env)

    @property
    def client(self):
        if self._client is None:
            try:
                from dodopayments import DodoPayments
            except ImportError as e:
                raise BillingConfigurationError(
                    'The dodopayments package is not installed. Run: pip install dodopayments'
                ) from e
            self._client = DodoPayments(
                bearer_token=self._bearer_token,
                environment=self._environment,
            )
        return self._client

    def _interval_to_api(self, interval: str) -> str:
        if interval == 'monthly':
            return 'Month'
        if interval == 'yearly':
            return 'Year'
        raise ValueError(f'Unsupported billing interval for Dodo: {interval!r}')

    def create_subscription_product(
        self,
        *,
        plan: Plan,
        interval: str,
        amount_minor: int,
        currency: str,
        tax_category: str,
    ) -> str:
        unit = self._interval_to_api(interval)
        price = {
            'type': 'recurring_price',
            'currency': currency,
            'discount': 0,
            'purchasing_power_parity': False,
            'price': amount_minor,
            'payment_frequency_count': 1,
            'payment_frequency_interval': unit,
            'subscription_period_count': 1,
            'subscription_period_interval': unit,
            'trial_period_days': 0,
        }
        product = self.client.products.create(
            name=f'{plan.name} ({interval})',
            price=price,
            tax_category=tax_category,
            metadata={
                'resolvemeq_plan_id': str(plan.id),
                'resolvemeq_plan_slug': plan.slug,
                'billing_interval': interval,
            },
        )
        return product.product_id

    def create_checkout_session(
        self,
        *,
        product_id: str,
        customer_email: str,
        return_url: str,
        customer_name: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> CheckoutSessionResult:
        payload_metadata = metadata or {}
        customer: dict = {'email': customer_email}
        if customer_name:
            customer['name'] = customer_name
        resp = self.client.checkout_sessions.create(
            product_cart=[{'product_id': product_id, 'quantity': 1}],
            customer=customer,
            return_url=return_url,
            metadata=payload_metadata,
        )
        return CheckoutSessionResult(
            session_id=resp.session_id,
            checkout_url=resp.checkout_url,
        )
