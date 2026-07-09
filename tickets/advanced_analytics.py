"""Advanced analytics: deflection by category, confidence calibration, workflow bottlenecks (P4-5)."""

from __future__ import annotations

import statistics
from collections import defaultdict
from typing import Any, Dict, List, Optional

from django.db.models import QuerySet
from django.utils import timezone


def _bucket_confidence(value: Optional[float]) -> str:
    if value is None:
        return "unknown"
    if value < 0.3:
        return "0.0-0.3"
    if value < 0.6:
        return "0.3-0.6"
    if value < 0.8:
        return "0.6-0.8"
    return "0.8-1.0"


def compute_deflection_by_category(ticket_qs: QuerySet) -> List[Dict[str, Any]]:
    rows = list(
        ticket_qs.filter(agent_processed=True).values(
            "category", "status", "escalated_at"
        )
    )
    by_cat: Dict[str, Dict[str, int]] = defaultdict(lambda: {"processed": 0, "deflected": 0})
    for row in rows:
        cat = row["category"] or "other"
        by_cat[cat]["processed"] += 1
        if row["status"] == "resolved" and row["escalated_at"] is None:
            by_cat[cat]["deflected"] += 1
    out = []
    for category, counts in sorted(by_cat.items(), key=lambda x: -x[1]["processed"]):
        processed = counts["processed"]
        deflected = counts["deflected"]
        out.append({
            "category": category,
            "agent_processed_count": processed,
            "deflected_count": deflected,
            "deflection_rate_percent": round(100.0 * deflected / processed, 1) if processed else None,
        })
    return out


def compute_confidence_calibration(ticket_qs: QuerySet) -> List[Dict[str, Any]]:
    from tickets.models import AgentConfidenceLog, TicketResolution

    ticket_ids = list(ticket_qs.values_list("ticket_id", flat=True))
    if not ticket_ids:
        return []

    resolutions = {
        r.ticket_id: r
        for r in TicketResolution.objects.filter(ticket_id__in=ticket_ids)
    }
    tickets = {
        t.ticket_id: t
        for t in ticket_qs.filter(ticket_id__in=ticket_ids).only(
            "ticket_id", "status", "escalated_at"
        )
    }

    # Latest analyze confidence per ticket for calibration
    logs = (
        AgentConfidenceLog.objects.filter(
            ticket_id__in=ticket_ids,
            source=AgentConfidenceLog.SOURCE_ANALYZE,
        )
        .order_by("ticket_id", "-created_at")
        .values("ticket_id", "confidence", "recommended_action")
    )
    seen = set()
    bucket_stats: Dict[str, Dict[str, int]] = defaultdict(
        lambda: {"samples": 0, "resolved_no_escalation": 0, "escalated": 0, "reopened": 0}
    )
    for log in logs:
        tid = log["ticket_id"]
        if tid in seen:
            continue
        seen.add(tid)
        bucket = _bucket_confidence(log["confidence"])
        bucket_stats[bucket]["samples"] += 1
        ticket = tickets.get(tid)
        if not ticket:
            continue
        if ticket.status == "resolved" and ticket.escalated_at is None:
            bucket_stats[bucket]["resolved_no_escalation"] += 1
        if ticket.escalated_at is not None:
            bucket_stats[bucket]["escalated"] += 1
        res = resolutions.get(tid)
        if res and res.reopened:
            bucket_stats[bucket]["reopened"] += 1

    order = ["0.8-1.0", "0.6-0.8", "0.3-0.6", "0.0-0.3", "unknown"]
    out = []
    for bucket in order:
        if bucket not in bucket_stats:
            continue
        s = bucket_stats[bucket]
        n = s["samples"]
        out.append({
            "confidence_bucket": bucket,
            "samples": n,
            "resolved_without_escalation_rate_percent": (
                round(100.0 * s["resolved_no_escalation"] / n, 1) if n else None
            ),
            "escalation_rate_percent": round(100.0 * s["escalated"] / n, 1) if n else None,
            "reopen_rate_percent": round(100.0 * s["reopened"] / n, 1) if n else None,
        })
    return out


def compute_workflow_bottlenecks(workflow_qs: QuerySet, *, limit: int = 10) -> List[Dict[str, Any]]:
    from workflows.models import WorkflowStep

    workflow_ids = list(workflow_qs.values_list("id", flat=True))
    if not workflow_ids:
        return []

    now = timezone.now()
    steps = WorkflowStep.objects.filter(workflow_id__in=workflow_ids).select_related("workflow")
    by_title: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {
            "completion_hours": [],
            "active_now": 0,
            "overdue_now": 0,
            "completed": 0,
        }
    )
    for step in steps:
        key = step.title or f"Step {step.order_index}"
        entry = by_title[key]
        if step.status == "done" and step.completed_at and step.workflow.created_at:
            hours = (step.completed_at - step.workflow.created_at).total_seconds() / 3600.0
            entry["completion_hours"].append(hours)
            entry["completed"] += 1
        elif step.status == "active":
            entry["active_now"] += 1
            if step.due_at and step.due_at < now:
                entry["overdue_now"] += 1

    ranked = []
    for title, data in by_title.items():
        hours = data["completion_hours"]
        median_hours = float(statistics.median(hours)) if hours else None
        ranked.append({
            "step_title": title,
            "completed_count": data["completed"],
            "active_now": data["active_now"],
            "overdue_now": data["overdue_now"],
            "median_hours_from_workflow_start": round(median_hours, 2) if median_hours is not None else None,
            "bottleneck_score": (data["overdue_now"] * 10) + data["active_now"] + (median_hours or 0),
        })
    ranked.sort(key=lambda x: (-x["bottleneck_score"], -x["overdue_now"], -x["active_now"]))
    return ranked[:limit]


def compute_advanced_analytics(*, ticket_qs: QuerySet, workflow_qs: QuerySet) -> Dict[str, Any]:
    routing = None
    try:
        from tickets.predictive_routing import get_routing_metrics

        routing = get_routing_metrics()
    except Exception:
        routing = None

    return {
        "generated_at": timezone.now().isoformat(),
        "deflection_by_category": compute_deflection_by_category(ticket_qs),
        "confidence_calibration": compute_confidence_calibration(ticket_qs),
        "workflow_bottlenecks": compute_workflow_bottlenecks(workflow_qs),
        "predictive_routing": routing,
    }
