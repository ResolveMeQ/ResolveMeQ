from decimal import Decimal


def decimal_to_minor_units(amount: Decimal) -> int:
    """Convert a major-unit decimal (e.g. USD dollars) to minor units (e.g. cents)."""
    if amount < 0:
        raise ValueError('amount must be non-negative')
    return int((amount * 100).quantize(Decimal('1')))
