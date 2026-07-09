"""Heuristic + history assignee routing before LLM (P4-3)."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any, Dict, List, Optional

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

OPEN_STATUSES = ("new", "open", "pending", "escalated", "in_progress", "assigned", "pending_clarification")
CACHE_METRICS = "predictive_routing:metrics"


def _routing_enabled() -> bool:
    return bool(getattr(settings, "PREDICTIVE_ROUTING_ENABLED", True))


def _lookback_days() -> int:
    return int(getattr(settings, "PREDICTIVE_ROUTING_LOOKBACK_DAYS", 90))


def _auto_assign_min_confidence() -> float:
    return float(getattr(settings, "PREDICTIVE_ROUTING_AUTO_ASSIGN_MIN_CONFIDENCE", 0.55))


def _team_candidates(team, *, exclude_user_id=None):
    from base.models import Team

    if not team or not isinstance(team, Team):
        return []
    user_ids = set()
    if team.owner_id:
        user_ids.add(team.owner_id)
    user_ids.update(team.members.values_list("id", flat=True))
    if exclude_user_id:
        user_ids.discard(exclude_user_id)
    if not user_ids:
        return []
    from base.models import User

    return list(User.objects.filter(pk__in=user_ids, is_active=True))


def _score_assignee(user, ticket, *, lookback_start) -> Dict[str, Any]:
    from tickets.models import Ticket

    team_id = ticket.team_id
    category = ticket.category or "other"
    resolved_category = Ticket.objects.filter(
        team_id=team_id,
        assigned_to_id=user.id,
        category=category,
        status="resolved",
        updated_at__gte=lookback_start,
    ).count()
    resolved_total = Ticket.objects.filter(
        team_id=team_id,
        assigned_to_id=user.id,
        status="resolved",
        updated_at__gte=lookback_start,
    ).count()
    open_workload = Ticket.objects.filter(
        team_id=team_id,
        assigned_to_id=user.id,
        status__in=OPEN_STATUSES,
    ).count()
    score = (resolved_category * 10) + (resolved_total * 2) - (open_workload * 4)
    if team_id and getattr(ticket, "team", None) and ticket.team.owner_id == user.id:
        score += 1
    return {
        "user_id": str(user.id),
        "name": user.get_full_name() or user.email or user.username,
        "email": user.email,
        "score": score,
        "resolved_in_category": resolved_category,
        "resolved_total": resolved_total,
        "open_workload": open_workload,
    }


def suggest_assignee(ticket) -> Optional[Dict[str, Any]]:
    """Return ranked routing suggestion for a team-scoped ticket."""
    if not _routing_enabled() or not ticket.team_id:
        return None

    candidates = _team_candidates(ticket.team, exclude_user_id=ticket.user_id)
    if not candidates:
        return None

    lookback_start = timezone.now() - timedelta(days=_lookback_days())
    ranked = sorted(
        (_score_assignee(user, ticket, lookback_start=lookback_start) for user in candidates),
        key=lambda row: row["score"],
        reverse=True,
    )
    top = ranked[0]
    second_score = ranked[1]["score"] if len(ranked) > 1 else 0
    margin = top["score"] - second_score
    if top["score"] <= 0 and len(candidates) == 1:
        confidence = 0.5
    elif top["score"] <= 0:
        confidence = 0.35
    else:
        confidence = min(1.0, (margin + 5) / (abs(top["score"]) + 5))

    reasons = []
    if top["resolved_in_category"]:
        reasons.append(
            f"Resolved {top['resolved_in_category']} {ticket.category or 'similar'} ticket(s) recently"
        )
    if top["open_workload"] == 0:
        reasons.append("No open assigned tickets")
    elif top["open_workload"] <= 2:
        reasons.append(f"Light workload ({top['open_workload']} open)")
    if not reasons:
        reasons.append("Best available team member by workload and category history")

    return {
        "suggested_assignee_id": top["user_id"],
        "suggested_assignee_name": top["name"],
        "confidence": round(confidence, 3),
        "score": top["score"],
        "margin": margin,
        "reasons": reasons[:4],
        "candidates": ranked[:5],
        "category": ticket.category,
        "auto_assigned": False,
    }


def _load_metrics() -> Dict[str, int]:
    data = cache.get(CACHE_METRICS)
    return data if isinstance(data, dict) else {
        "routing_applied": 0,
        "routing_reassigned": 0,
    }


def _save_metrics(data: Dict[str, int]) -> None:
    cache.set(CACHE_METRICS, data, timeout=86400 * 30)


def record_routing_applied() -> None:
    metrics = _load_metrics()
    metrics["routing_applied"] = int(metrics.get("routing_applied", 0)) + 1
    _save_metrics(metrics)


def record_routing_reassignment(ticket, previous_assignee_id, new_assignee_id) -> None:
    if not previous_assignee_id or str(previous_assignee_id) == str(new_assignee_id):
        return
    from tickets.models import ActionHistory

    predictive = (
        ActionHistory.objects.filter(ticket=ticket, action_type="PREDICTIVE_ROUTE")
        .order_by("-executed_at")
        .first()
    )
    if not predictive:
        return
    suggested_id = (predictive.action_params or {}).get("suggested_assignee_id")
    if suggested_id and str(suggested_id) == str(previous_assignee_id):
        metrics = _load_metrics()
        metrics["routing_reassigned"] = int(metrics.get("routing_reassigned", 0)) + 1
        _save_metrics(metrics)


def get_routing_metrics() -> Dict[str, Any]:
    metrics = _load_metrics()
    applied = int(metrics.get("routing_applied", 0))
    reassigned = int(metrics.get("routing_reassigned", 0))
    return {
        **metrics,
        "reassignment_rate": round(reassigned / applied, 4) if applied else None,
    }


def maybe_apply_predictive_routing(ticket, *, auto_assign: bool = True) -> Optional[Dict[str, Any]]:
    """
    Suggest and optionally pre-assign an agent before LLM processing.
    Returns the suggestion dict when evaluated.
    """
    if not _routing_enabled() or ticket.assigned_to_id or not ticket.team_id:
        return None

    suggestion = suggest_assignee(ticket)
    if not suggestion:
        return None

    should_assign = (
        auto_assign
        and suggestion["confidence"] >= _auto_assign_min_confidence()
        and suggestion["score"] >= 0
    )
    if not should_assign:
        return suggestion

    from base.models import User
    from tickets.models import ActionHistory

    assignee = User.objects.filter(pk=suggestion["suggested_assignee_id"]).first()
    if not assignee:
        return suggestion

    from tickets.scoping import user_can_assign_agent

    if not user_can_assign_agent(ticket, assignee):
        return suggestion

    ticket.assigned_to = assignee
    if ticket.status == "new":
        ticket.status = "assigned"
    ticket.save(update_fields=["assigned_to", "status", "updated_at"])

    suggestion = {**suggestion, "auto_assigned": True}
    ActionHistory.objects.create(
        ticket=ticket,
        action_type="PREDICTIVE_ROUTE",
        action_params=suggestion,
        executed_by="predictive_routing",
        agent_reasoning="; ".join(suggestion.get("reasons") or []),
        rollback_possible=True,
        rollback_steps={"handler": "rollback_predictive_route"},
        before_state={"assigned_to_id": None, "status": "new"},
        after_state={
            "assigned_to_id": str(assignee.id),
            "status": ticket.status,
        },
    )
    record_routing_applied()
    logger.info(
        "Predictive routing assigned ticket %s to %s (confidence=%.2f)",
        ticket.ticket_id,
        assignee.email,
        suggestion["confidence"],
    )
    return suggestion


def routing_suggestion_for_api(ticket) -> Optional[Dict[str, Any]]:
    """Lightweight payload for ticket APIs."""
    suggestion = suggest_assignee(ticket)
    if not suggestion:
        return None
    return {
        "assignee_id": suggestion["suggested_assignee_id"],
        "assignee_name": suggestion["suggested_assignee_name"],
        "confidence": suggestion["confidence"],
        "reasons": suggestion["reasons"],
        "auto_assigned": suggestion.get("auto_assigned", False),
    }
