"""Metrics for curated playbook SKUs."""

from __future__ import annotations

from typing import Any, Dict

from django.db.models import Q
from django.utils import timezone


def compute_onboarding_playbook_metrics(workflows_qs) -> Dict[str, Any]:
    """Onboarding template workflows: started, completed, in progress, overdue, completion rate."""
    now = timezone.now()
    onboarding = workflows_qs.filter(template__trigger_category="onboarding")
    started = onboarding.count()
    completed = onboarding.filter(status="completed").count()
    in_progress = onboarding.filter(status="in_progress").count()
    overdue = onboarding.filter(
        Q(status="in_progress", due_at__lt=now)
        | Q(steps__status="active", steps__due_at__lt=now)
    ).distinct().count()
    completion_rate = round(100.0 * completed / started, 1) if started else None
    return {
        "playbook_id": "employee-onboarding",
        "workflows_started": started,
        "workflows_completed": completed,
        "workflows_in_progress": in_progress,
        "workflows_overdue": overdue,
        "completion_rate_percent": completion_rate,
    }
