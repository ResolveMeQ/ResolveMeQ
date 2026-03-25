"""Aggregate outcome metrics for scoped ticket querysets."""

from __future__ import annotations

import statistics
from collections import defaultdict
from typing import Any, Dict, List, Optional

from django.db.models import QuerySet


def _median(xs: List[float]) -> Optional[float]:
    if not xs:
        return None
    return float(statistics.median(xs))


def compute_outcome_metrics(queryset: QuerySet) -> Dict[str, Any]:
    """
    - median_seconds_to_first_ai: among tickets with first_ai_at set
    - pct_resolved_without_escalation: share of agent-processed resolved tickets never escalated
    - deflection_rate: among agent-processed tickets, fraction with status resolved and escalated_at null
    - by_team: per-team breakdown (team_id may be null)
    """
    rows = list(
        queryset.values(
            "ticket_id",
            "team_id",
            "created_at",
            "first_ai_at",
            "escalated_at",
            "status",
            "agent_processed",
        )
    )

    deltas: List[float] = []
    for r in rows:
        c, f = r["created_at"], r["first_ai_at"]
        if c and f:
            deltas.append((f - c).total_seconds())

    agent_processed = [r for r in rows if r["agent_processed"]]
    resolved = [r for r in agent_processed if r["status"] == "resolved"]
    resolved_never_escalated = [r for r in resolved if r["escalated_at"] is None]
    pct_resolved_no_esc = (
        100.0 * len(resolved_never_escalated) / len(resolved) if resolved else None
    )

    # Deflection: closed by AI path without escalation record
    deflected = [r for r in agent_processed if r["status"] == "resolved" and r["escalated_at"] is None]
    deflection_rate = 100.0 * len(deflected) / len(agent_processed) if agent_processed else None

    by_team: Dict[Any, Dict[str, Any]] = defaultdict(
        lambda: {
            "ticket_count": 0,
            "seconds_to_first_ai": [],
            "agent_processed": 0,
            "resolved_without_escalation": 0,
        }
    )
    for r in rows:
        tid = r["team_id"]
        by_team[tid]["ticket_count"] += 1
        if r["created_at"] and r["first_ai_at"]:
            by_team[tid]["seconds_to_first_ai"].append((r["first_ai_at"] - r["created_at"]).total_seconds())
        if r["agent_processed"]:
            by_team[tid]["agent_processed"] += 1
            if r["status"] == "resolved" and r["escalated_at"] is None:
                by_team[tid]["resolved_without_escalation"] += 1

    by_team_out: List[Dict[str, Any]] = []
    for team_id, v in sorted(by_team.items(), key=lambda x: (x[0] is None, x[0])):
        secs = v["seconds_to_first_ai"]
        ap = v["agent_processed"]
        rwe = v["resolved_without_escalation"]
        by_team_out.append(
            {
                "team_id": team_id,
                "ticket_count": v["ticket_count"],
                "median_seconds_to_first_ai": _median(secs),
                "agent_processed_count": ap,
                "pct_resolved_without_escalation": (100.0 * rwe / ap) if ap else None,
            }
        )

    return {
        "sample_size": len(rows),
        "median_seconds_to_first_ai": _median(deltas),
        "pct_resolved_without_escalation": pct_resolved_no_esc,
        "deflection_rate_percent": deflection_rate,
        "agent_processed_count": len(agent_processed),
        "by_team": by_team_out,
    }
