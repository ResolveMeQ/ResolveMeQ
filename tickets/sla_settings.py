"""Configurable escalation SLA hours per priority (mirrors confidence_settings.py)."""

from django.conf import settings

_DEFAULT_SLA_HOURS = {"critical": 2, "high": 8, "medium": 24, "low": 48}


def escalation_sla_hours(priority):
    overrides = getattr(settings, "ESCALATION_SLA_HOURS", {}) or {}
    hours = overrides.get(priority, _DEFAULT_SLA_HOURS.get(priority, _DEFAULT_SLA_HOURS["medium"]))
    return float(hours)
