"""Configurable agent confidence thresholds (defaults preserve legacy 0.8 / 0.6 / 0.3)."""

from django.conf import settings


def agent_confidence_high():
    return float(getattr(settings, "AGENT_CONFIDENCE_HIGH", 0.8))


def agent_confidence_medium():
    return float(getattr(settings, "AGENT_CONFIDENCE_MEDIUM", 0.6))


def agent_confidence_low():
    return float(getattr(settings, "AGENT_CONFIDENCE_LOW", 0.3))


def agent_success_prob_auto_resolve():
    """Minimum solution success probability to allow auto_resolve at high confidence."""
    return float(getattr(settings, "AGENT_SUCCESS_PROB_AUTO_RESOLVE", 0.8))
