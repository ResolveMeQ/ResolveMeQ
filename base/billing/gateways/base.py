from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from base.models import Plan


@dataclass
class CheckoutSessionResult:
    session_id: str
    checkout_url: str | None


class BillingGateway(ABC):
    """Provider-agnostic checkout and catalog operations."""

    code: str

    @abstractmethod
    def create_subscription_product(
        self,
        *,
        plan: Plan,
        interval: str,
        amount_minor: int,
        currency: str,
        tax_category: str,
    ) -> str:
        """Create a recurring product in the provider; return external product id."""

    @abstractmethod
    def create_checkout_session(
        self,
        *,
        product_id: str,
        customer_email: str,
        return_url: str,
        customer_name: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> CheckoutSessionResult:
        """Start a hosted checkout for the given subscription product."""
