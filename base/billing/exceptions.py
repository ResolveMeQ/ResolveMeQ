class BillingConfigurationError(RuntimeError):
    """Raised when billing is misconfigured (e.g. missing API keys)."""


class SubscriptionSyncError(RuntimeError):
    """Raised when a provider subscription payload cannot be applied (e.g. unknown user)."""

