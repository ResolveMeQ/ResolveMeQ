from django.conf import settings

from base.billing.exceptions import BillingConfigurationError
from base.billing.gateways.base import BillingGateway


def get_billing_gateway() -> BillingGateway:
    code = (getattr(settings, 'BILLING_GATEWAY', 'dodo') or 'dodo').strip().lower()
    if code == 'dodo':
        from base.billing.gateways.dodo import DodoGateway

        return DodoGateway.from_settings()
    raise BillingConfigurationError(f'Unsupported BILLING_GATEWAY: {code!r}')
