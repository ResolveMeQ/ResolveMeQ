"""Timestamps and confidence logging for outcome metrics and calibration."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

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


def steps_from_agent_response(
    agent_response: Any,
    solution: Optional[Dict[str, Any]] = None,
) -> List[str]:
    """
    Extract resolution steps from an AI-agent JSON response using one
    canonical precedence order: ``solution.steps`` -> ``resolution_steps`` ->
    ``steps``.

    This matches ``solution.get("steps")`` used first in
    ``autonomous_agent.py`` (it's what ``resolution_steps`` gets populated
    from when building AUTO_RESOLVE params) and in the Slack/Teams solution
    renderers (``integrations/views.py``, ``integrations/teams_views.py``) --
    ``solution.steps`` is the agent's structured, authoritative field;
    ``resolution_steps``/top-level ``steps`` are looser/legacy keys some
    agent responses use instead.

    `agent_response` is the raw dict returned by the AI agent (analyze or
    chat). `solution` is an optional dict already extracted from
    ``agent_response.get("solution")`` -- pass it if the caller already has
    it, otherwise it's read from `agent_response`.

    Always returns a list of non-empty, stripped step strings (never a bare
    string), or `[]` if nothing usable was found. Callers that need a single
    text blob (e.g. ``Solution.steps``, a TextField) should
    ``"\\n".join(...)`` the result.
    """
    if not isinstance(agent_response, dict):
        return []
    if solution is None:
        solution = agent_response.get("solution") or {}
    if not isinstance(solution, dict):
        solution = {}
    raw = (
        solution.get("steps")
        or agent_response.get("resolution_steps")
        or agent_response.get("steps")
    )
    if not raw:
        return []
    if isinstance(raw, str):
        text = raw.strip()
        return [text] if text else []
    if isinstance(raw, list):
        return [str(s).strip() for s in raw if str(s).strip()]
    return []
