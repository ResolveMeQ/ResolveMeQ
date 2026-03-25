"""Structured human handoff context for escalations."""

from __future__ import annotations

from typing import Any, Dict

from .models import Ticket


def build_handoff_packet(ticket: Ticket, user, conversation_summary: str = "") -> Dict[str, Any]:
    """
    Build a structured handoff plus a plain-text block for email/Slack.
    `user` is the actor (requester on agent-driven escalation, or the user who clicked escalate).
    """
    ar = ticket.agent_response if isinstance(ticket.agent_response, dict) else {}
    confidence = ar.get("confidence")
    try:
        conf_f = float(confidence) if confidence is not None else None
    except (TypeError, ValueError):
        conf_f = None
    rec = (ar.get("recommended_action") or "").strip()
    who = getattr(user, "email", None) or getattr(user, "username", None) or str(getattr(user, "pk", user))
    summary = (conversation_summary or "").strip()[:2000]
    desc = (ticket.description or "").strip()
    desc_short = desc[:500] + ("…" if len(desc) > 500 else "")

    lines = [
        f"Ticket #{ticket.ticket_id} — {ticket.issue_type or 'Support'}",
        f"Category: {ticket.category or '—'} · Status: {ticket.status}",
        f"Requester: {getattr(ticket.user, 'email', None) or getattr(ticket.user, 'username', '')}",
        f"Escalation context from: {who}",
    ]
    if conf_f is not None:
        lines.append(f"Last analyze confidence: {conf_f:.2f}")
    if rec:
        lines.append(f"Recommended action (analyze): {rec}")
    if desc_short:
        lines.append(f"Description: {desc_short}")
    if summary:
        lines.append(f"Conversation / user notes: {summary}")

    handoff_text = "\n".join(lines)
    handoff_summary = handoff_text[:400] + ("…" if len(handoff_text) > 400 else "")

    return {
        "ticket_id": ticket.ticket_id,
        "issue_type": ticket.issue_type,
        "category": ticket.category,
        "status": ticket.status,
        "analyze_confidence": conf_f,
        "recommended_action": rec,
        "conversation_summary": summary,
        "handoff_text": handoff_text,
        "handoff_summary": handoff_summary,
    }
