"""Workflow step AI assistant — LLM + KB (P3-1)."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

import requests
from django.conf import settings

from base.agent_http import get_agent_service_headers
from base.agent_usage import refund_agent_operation, try_consume_agent_operation

logger = logging.getLogger(__name__)


def _linked_kb_for_step(workflow, step) -> List[Dict[str, Any]]:
    from workflows.kb_links import resolve_kb_articles_by_titles

    template = workflow.template
    if not template:
        return []
    steps = template.steps or []
    idx = step.order_index
    if idx < 0 or idx >= len(steps):
        return []
    return resolve_kb_articles_by_titles(steps[idx].get("kb_links") or [])


def _resolution_template_hints(workflow) -> List[Dict[str, Any]]:
    from workflows.playbook_assets import resolve_resolution_templates_by_names
    from workflows.playbooks.employee_onboarding import ONBOARDING_RESOLUTION_TEMPLATE_NAME

    if not workflow.template_id:
        return []
    if (workflow.template.trigger_category or "") != "onboarding":
        return []
    return resolve_resolution_templates_by_names([ONBOARDING_RESOLUTION_TEMPLATE_NAME])


def _build_step_guidance(workflow, step, ticket) -> str:
    ticket_line = ""
    if ticket:
        ticket_line = (
            f"Linked ticket #{ticket.ticket_id}: {ticket.issue_type or 'support'} — "
            f"{(ticket.description or '')[:300]}"
        )
    return (
        "WORKFLOW STEP ASSISTANT MODE:\n"
        f"- Active playbook step: \"{step.title}\"\n"
        f"- Step instructions: {(step.description or '').strip()[:800]}\n"
        f"- Step type: {step.step_type or 'manual'}\n"
        + (f"- {ticket_line}\n" if ticket_line else "")
        + "- Help the assignee complete THIS step only. Do not invent new workflow steps.\n"
        "- Ground advice in KB articles when available; cite them. General IT guidance is OK when KB is thin.\n"
        "- Return actionable sub-steps the assignee can do right now for this workflow step."
    )


def _build_rag_query(workflow, step, ticket) -> str:
    parts = [step.title or "", step.description or ""]
    if ticket:
        parts.extend([
            ticket.issue_type or "",
            ticket.category or "",
            (ticket.description or "")[:400],
        ])
    if workflow.template_id and workflow.template:
        parts.append(workflow.template.name or "")
    query = " ".join(p.strip() for p in parts if p and p.strip())
    return query[:700] if query else "IT workflow step guidance"


def _normalize_citations(raw: Any) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not isinstance(raw, list):
        return out
    for item in raw:
        if not isinstance(item, dict):
            continue
        kb_id = item.get("kb_id") or item.get("id")
        title = item.get("title") or item.get("article_title")
        if kb_id and title:
            out.append({
                "kb_id": str(kb_id),
                "title": str(title),
                "excerpt": (item.get("excerpt") or item.get("snippet") or "")[:400],
                "url": item.get("url") or f"/knowledge-base?kb={kb_id}",
            })
    return out


def _merge_citations(*groups: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    merged: List[Dict[str, Any]] = []
    seen = set()
    for group in groups:
        for item in group:
            key = item.get("kb_id") or item.get("title")
            if not key or key in seen:
                continue
            seen.add(key)
            merged.append(item)
    return merged


def _fallback_suggestions(workflow, step, linked_kb: List[Dict[str, Any]]) -> Dict[str, Any]:
    resolution_templates = _resolution_template_hints(workflow)
    actions: List[str] = []
    if step.description:
        actions.append(step.description.strip())
    for kb in linked_kb[:3]:
        actions.append(f"Review KB: {kb.get('title')}")
    return {
        "summary": step.description or f"Complete the step: {step.title}",
        "actions": actions[:6],
        "kb_citations": linked_kb,
        "resolution_templates": resolution_templates,
        "source": "fallback",
        "agent_used": False,
    }


def _call_agent_for_step(*, workflow, step, ticket, user) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    agent_url = getattr(settings, "AI_AGENT_URL", "https://agent.resolvemeq.net/tickets/analyze/")
    ticket_id = ticket.ticket_id if ticket else 0
    user_info = {
        "id": str(user.id),
        "name": user.get_full_name() or user.username or user.email,
        "department": getattr(user, "department", "") or "",
    }
    payload = {
        "ticket_id": ticket_id,
        "issue_type": ticket.issue_type if ticket else step.title,
        "description": (
            f"Workflow step assistance requested.\n\n"
            f"Step: {step.title}\n"
            f"Instructions: {step.description or '(none)'}\n"
            f"Playbook: {workflow.template.name if workflow.template_id else 'Workflow'}"
        ),
        "category": ticket.category if ticket else "other",
        "tags": list(ticket.tags or []) if ticket else ["workflow", "step_assistant"],
        "user": user_info,
        "conversation_guidance": _build_step_guidance(workflow, step, ticket),
        "rag_search_query": _build_rag_query(workflow, step, ticket),
        "latest_user_message": f"Help me complete this workflow step: {step.title}",
        "is_chat_follow_up": False,
        "conversation_turn": 1,
    }
    if ticket and ticket.screenshot:
        payload["screenshot"] = ticket.screenshot

    resp = requests.post(
        agent_url,
        json=payload,
        headers=get_agent_service_headers(),
        timeout=25,
    )
    resp.raise_for_status()
    return resp.json(), None


def get_step_assistant_suggestions(*, workflow, step, user) -> Dict[str, Any]:
    """
    Return LLM+KB guidance for an active workflow step.
    Falls back to linked KB + step description when agent is unavailable.
    """
    from workflows.models import WorkflowStepAssistantEvent

    if step.status != "active":
        return {"error": "Suggestions are only available for the active step."}

    linked_kb = _linked_kb_for_step(workflow, step)
    resolution_templates = _resolution_template_hints(workflow)
    ticket = workflow.ticket

    charged = False
    agent_data = None
    agent_error = None
    try:
        quota = try_consume_agent_operation(user)
        if not quota.allowed:
            return {
                "error": "agent_quota_exceeded",
                "detail": "Your plan monthly AI agent limit has been reached.",
                "agent_operations_used": quota.used,
                "agent_operations_limit": quota.limit,
            }
        charged = True
        agent_data, agent_error = _call_agent_for_step(
            workflow=workflow, step=step, ticket=ticket, user=user
        )
    except requests.RequestException as exc:
        agent_error = str(exc)
        logger.warning("Step assistant agent call failed: %s", exc)
        if charged:
            refund_agent_operation(user)
            charged = False
    except Exception as exc:
        agent_error = str(exc)
        logger.warning("Step assistant failed: %s", exc)
        if charged:
            refund_agent_operation(user)

    if not agent_data:
        result = _fallback_suggestions(workflow, step, linked_kb)
        result["agent_error"] = agent_error
        WorkflowStepAssistantEvent.objects.create(
            step=step,
            user=user,
            event_type=WorkflowStepAssistantEvent.EVENT_VIEWED,
            payload={"source": result.get("source"), "fallback": True},
        )
        return result

    reasoning = (agent_data.get("reasoning") or "").strip()
    solution = agent_data.get("solution") or {}
    steps_raw = solution.get("steps") if isinstance(solution, dict) else []
    actions = [str(s).strip() for s in (steps_raw or []) if str(s).strip()][:8]
    kb_citations = _merge_citations(
        linked_kb,
        _normalize_citations(agent_data.get("kb_article_citations")),
    )

    result = {
        "summary": reasoning or step.description or f"Guidance for {step.title}",
        "actions": actions,
        "kb_citations": kb_citations,
        "resolution_templates": resolution_templates,
        "confidence": agent_data.get("confidence"),
        "source": "llm_kb",
        "agent_used": True,
    }
    WorkflowStepAssistantEvent.objects.create(
        step=step,
        user=user,
        event_type=WorkflowStepAssistantEvent.EVENT_VIEWED,
        payload={"source": "llm_kb", "confidence": result.get("confidence")},
    )
    return result


def accept_step_assistant_suggestion(*, workflow, step, user, note: str) -> Dict[str, Any]:
    """Record acceptance and optionally add an internal note on the linked ticket."""
    from tickets.models import TicketInteraction
    from workflows.models import WorkflowStepAssistantEvent

    text = (note or "").strip()
    if not text:
        return {"error": "note is required"}

    WorkflowStepAssistantEvent.objects.create(
        step=step,
        user=user,
        event_type=WorkflowStepAssistantEvent.EVENT_ACCEPTED,
        payload={"note_length": len(text)},
    )

    if workflow.ticket_id:
        TicketInteraction.objects.create(
            ticket=workflow.ticket,
            user=user,
            interaction_type="user_message",
            content=f"Workflow step note ({step.title}): {text[:8000]}",
        )
    return {"accepted": True, "step_id": step.id}
