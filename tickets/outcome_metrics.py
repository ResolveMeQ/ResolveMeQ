"""Aggregate outcome metrics for scoped ticket querysets."""

from __future__ import annotations

import statistics
from collections import defaultdict
from typing import Any, Dict, List, Optional

from django.db.models import QuerySet
from django.utils import timezone

OPEN_STATUSES = ("new", "open", "pending", "escalated", "in_progress", "assigned", "pending_clarification")


def _median(xs: List[float]) -> Optional[float]:
    if not xs:
        return None
    return float(statistics.median(xs))


def get_stuck_items(ticket_qs: QuerySet, workflow_qs: QuerySet, *, limit: int = 5) -> Dict[str, Any]:
    """
    "What's stuck right now" for the Dashboard: open tickets nobody has touched in a
    while, and active workflow steps whose due_at has already passed. Reuses the same
    scoped querysets outcome_metrics already builds -- no extra permission logic.
    """
    from workflows.models import WorkflowStep

    now = timezone.now()
    stuck_cutoff = now - timezone.timedelta(hours=24)

    stuck_qs = (
        ticket_qs.filter(status__in=OPEN_STATUSES, updated_at__lt=stuck_cutoff)
        .select_related("assigned_to")
        .order_by("updated_at")[:limit]
    )
    stuck_tickets = [
        {
            "ticket_id": t.ticket_id,
            "issue_type": t.issue_type,
            "status": t.status,
            "hours_idle": round((now - t.updated_at).total_seconds() / 3600.0, 1),
            "assigned_to_name": (t.assigned_to.get_full_name() or t.assigned_to.email) if t.assigned_to else None,
        }
        for t in stuck_qs
    ]

    workflow_ids = list(workflow_qs.filter(status="in_progress").values_list("id", flat=True))
    stalled_steps = []
    if workflow_ids:
        overdue_steps = (
            WorkflowStep.objects.filter(
                workflow_id__in=workflow_ids, status="active", due_at__lt=now,
            )
            .select_related("workflow", "workflow__ticket")
            .order_by("due_at")[:limit]
        )
        stalled_steps = [
            {
                "workflow_id": str(s.workflow_id),
                "ticket_id": s.workflow.ticket_id if s.workflow.ticket_id else None,
                "step_title": s.title,
                "hours_overdue": round((now - s.due_at).total_seconds() / 3600.0, 1),
            }
            for s in overdue_steps
        ]

    return {
        "stuck_tickets": stuck_tickets,
        "stuck_ticket_count": ticket_qs.filter(status__in=OPEN_STATUSES, updated_at__lt=stuck_cutoff).count(),
        "stalled_steps": stalled_steps,
        "stalled_step_count": (
            WorkflowStep.objects.filter(workflow_id__in=workflow_ids, status="active", due_at__lt=now).count()
            if workflow_ids else 0
        ),
    }


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
