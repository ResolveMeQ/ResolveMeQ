"""Timestamps and confidence logging for outcome metrics and calibration."""

from __future__ import annotations

from typing import Any, Optional

from django.utils import timezone

from .models import AgentConfidenceLog, Ticket


def touch_first_ai_at(ticket: Ticket) -> None:
    """Set first_ai_at once when the ticket first receives AI output."""
    if ticket.first_ai_at:
        return
    now = timezone.now()
    updated = Ticket.objects.filter(pk=ticket.pk, first_ai_at__isnull=True).update(first_ai_at=now)
    if updated:
        ticket.first_ai_at = now


def apply_escalated_timestamp(ticket: Ticket) -> None:
    """Set escalated_at on the in-memory ticket before save (first escalation only)."""
    if ticket.escalated_at:
        return
    ticket.escalated_at = timezone.now()


def _float_confidence(raw: Any) -> Optional[float]:
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def log_agent_confidence_snapshot(
    ticket: Ticket,
    source: str,
    *,
    confidence: Any = None,
    recommended_action: str = "",
) -> None:
    AgentConfidenceLog.objects.create(
        ticket=ticket,
        source=source,
        confidence=_float_confidence(confidence),
        recommended_action=(recommended_action or "")[:120],
    )
