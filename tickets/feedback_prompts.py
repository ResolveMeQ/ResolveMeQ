"""Situational follow-up prompts for feedback (ticket + resolution state)."""

from __future__ import annotations

from typing import Any, Dict, List

from django.utils import timezone


def build_feedback_prompts(ticket, user) -> List[Dict[str, Any]]:
    """
    Return ordered prompts for in-app banners (higher priority first).
    Client may dismiss per session via localStorage; server state still drives resolution survey.
    """
    from .models import TicketResolution

    prompts: List[Dict[str, Any]] = []

    if ticket.status == "resolved":
        try:
            tr = TicketResolution.objects.get(ticket=ticket)
            if tr.response_received_at is None:
                prompts.append(
                    {
                        "id": "resolution_outcome",
                        "kind": "survey",
                        "priority": 100,
                        "title": "Did the resolution work?",
                        "message": "Quick feedback helps train the AI and improve support.",
                        "cta_label": "Share feedback",
                        "cta_action": "resolution_feedback",
                    }
                )
        except TicketResolution.DoesNotExist:
            prompts.append(
                {
                    "id": "resolution_outcome",
                    "kind": "survey",
                    "priority": 100,
                    "title": "Did the resolution work?",
                    "message": "Let us know if this ticket was solved to your satisfaction.",
                    "cta_label": "Share feedback",
                    "cta_action": "resolution_feedback",
                }
            )

    if ticket.status == "escalated":
        prompts.append(
            {
                "id": "escalation_context",
                "kind": "info",
                "priority": 60,
                "title": "Escalated to a human",
                "message": "Add any missing context in comments so support can move faster.",
                "cta_label": "Add context",
                "cta_action": "focus_comments",
            }
        )

    if ticket.status in ("in_progress", "open", "new", "pending_clarification"):
        age = timezone.now() - ticket.created_at
        if age.total_seconds() >= 3600 * 24 and ticket.agent_processed:
            prompts.append(
                {
                    "id": "long_running_check",
                    "kind": "check_in",
                    "priority": 40,
                    "title": "Still stuck?",
                    "message": "If this has been open a while, tell the AI what you’ve tried or escalate to a human.",
                    "cta_label": "Got it",
                    "cta_action": "dismiss_only",
                }
            )

    prompts.sort(key=lambda p: -p.get("priority", 0))
    return prompts
