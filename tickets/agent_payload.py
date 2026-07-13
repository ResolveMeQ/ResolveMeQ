"""Build JSON payloads for the FastAPI AI agent from Django tickets."""

from __future__ import annotations

from typing import Any, Dict


def build_ticket_agent_payload(ticket) -> Dict[str, Any]:
    """Base analyze/chat payload shared by Celery, sync, and chat reply paths."""
    payload: Dict[str, Any] = {
        "ticket_id": ticket.ticket_id,
        "issue_type": ticket.issue_type,
        "description": ticket.description or "",
        "category": ticket.category,
        "tags": ticket.tags or [],
        "user": {
            "id": str(ticket.user_id),
            "name": getattr(ticket.user, "username", "") or "",
            "department": getattr(ticket.user, "department", "") or "",
        },
    }
    if ticket.team_id:
        payload["team_id"] = str(ticket.team_id)
    if ticket.screenshot:
        payload["screenshot"] = ticket.screenshot
    if ticket.reported_platform:
        payload["reported_platform"] = ticket.reported_platform
    return payload
