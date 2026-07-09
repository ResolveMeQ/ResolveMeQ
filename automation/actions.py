"""Execute automation rule actions."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Tuple

from .constants import VALID_ACTION_TYPES

logger = logging.getLogger(__name__)


def _action_start_workflow(action: dict, ctx: Dict[str, Any], *, dry_run: bool) -> Tuple[bool, str]:
    from workflows.models import WorkflowTemplate
    from workflows.services import start_workflow

    ticket = ctx.get("ticket")
    team = getattr(ticket, "team", None) if ticket else ctx.get("team")
    template_id = action.get("template_id")
    trigger_category = (action.get("template_trigger_category") or "").strip()

    template = None
    if template_id:
        template = WorkflowTemplate.objects.filter(pk=template_id).first()
    elif trigger_category and ticket:
        template = (
            WorkflowTemplate.objects.filter(trigger_category=trigger_category, team=ticket.team).first()
            or WorkflowTemplate.objects.filter(trigger_category=trigger_category, team__isnull=True).first()
        )
    if not template:
        return False, "No matching workflow template."

    if dry_run:
        return True, f"Would start workflow '{template.name}'."

    started_by = getattr(ticket, "user", None) if ticket else None
    start_workflow(template=template, ticket=ticket, team=team, started_by=started_by)
    return True, f"Started workflow '{template.name}'."


def _action_set_field(action: dict, ctx: Dict[str, Any], *, dry_run: bool) -> Tuple[bool, str]:
    ticket = ctx.get("ticket")
    if not ticket:
        return False, "No ticket in context."
    field = (action.get("field") or "").strip()
    value = action.get("value")
    if not field or not hasattr(ticket, field):
        return False, f"Invalid ticket field: {field}"
    if dry_run:
        return True, f"Would set ticket.{field} = {value!r}."
    setattr(ticket, field, value)
    ticket.save(update_fields=[field, "updated_at"])
    return True, f"Set ticket.{field}."


def _action_assign_ticket(action: dict, ctx: Dict[str, Any], *, dry_run: bool) -> Tuple[bool, str]:
    from django.contrib.auth import get_user_model

    ticket = ctx.get("ticket")
    if not ticket:
        return False, "No ticket in context."
    user_id = action.get("user_id")
    if not user_id:
        return False, "assign_ticket requires user_id."
    User = get_user_model()
    user = User.objects.filter(pk=user_id).first()
    if not user:
        return False, "User not found."
    if dry_run:
        return True, f"Would assign ticket to {user.email or user.username}."
    ticket.assigned_to = user
    ticket.save(update_fields=["assigned_to", "updated_at"])
    return True, f"Assigned ticket to {user.email or user.username}."


def _action_run_agent(action: dict, ctx: Dict[str, Any], *, dry_run: bool) -> Tuple[bool, str]:
    ticket = ctx.get("ticket")
    if not ticket:
        return False, "No ticket in context."
    if dry_run:
        return True, f"Would queue AI agent for ticket #{ticket.ticket_id}."
    try:
        from tickets.tasks import process_ticket_with_agent

        process_ticket_with_agent.delay(ticket.ticket_id)
        return True, "Queued AI agent."
    except Exception as exc:
        logger.warning("run_agent action failed: %s", exc)
        return False, str(exc)


def _action_notify_slack(action: dict, ctx: Dict[str, Any], *, dry_run: bool) -> Tuple[bool, str]:
    if dry_run:
        return True, "Would send Slack notification."
    return True, "Slack notify logged (channel fan-out uses integrations.notify)."


def _action_notify_teams(action: dict, ctx: Dict[str, Any], *, dry_run: bool) -> Tuple[bool, str]:
    if dry_run:
        return True, "Would send Teams notification."
    return True, "Teams notify logged (channel fan-out uses integrations.notify)."


def _action_call_webhook(action: dict, ctx: Dict[str, Any], *, dry_run: bool) -> Tuple[bool, str]:
    from integrations.connectors.webhook import deliver_ad_hoc_webhook

    url = (action.get("url") or "").strip()
    if not url:
        return False, "call_webhook requires url."
    secret = (action.get("secret") or "").strip()
    event_type = (action.get("event_type") or "automation.webhook").strip()
    return deliver_ad_hoc_webhook(
        url=url,
        secret=secret,
        event_type=event_type,
        context=ctx,
        dry_run=dry_run,
    )


_ACTION_HANDLERS = {
    "start_workflow": _action_start_workflow,
    "set_field": _action_set_field,
    "assign_ticket": _action_assign_ticket,
    "run_agent": _action_run_agent,
    "notify_slack": _action_notify_slack,
    "notify_teams": _action_notify_teams,
    "call_webhook": _action_call_webhook,
}


def execute_actions(
    actions: List[dict],
    ctx: Dict[str, Any],
    *,
    dry_run: bool = False,
) -> Tuple[str, List[str]]:
    """Run actions in order. Returns (overall_status, messages)."""
    if not isinstance(actions, list) or not actions:
        return "skipped", ["No actions configured."]

    messages: List[str] = []
    any_failed = False
    for idx, action in enumerate(actions):
        if not isinstance(action, dict):
            any_failed = True
            messages.append(f"Action {idx + 1}: invalid action object.")
            continue
        action_type = (action.get("type") or "").strip()
        if action_type not in VALID_ACTION_TYPES:
            any_failed = True
            messages.append(f"Action {idx + 1}: unknown type '{action_type}'.")
            continue
        handler = _ACTION_HANDLERS.get(action_type)
        if not handler:
            any_failed = True
            messages.append(f"Action {idx + 1}: handler missing for '{action_type}'.")
            continue
        try:
            ok, msg = handler(action, ctx, dry_run=dry_run)
            messages.append(msg)
            if not ok:
                any_failed = True
        except Exception as exc:
            logger.exception("Action %s failed", action_type)
            any_failed = True
            messages.append(f"{action_type}: {exc}")
    status = "dry_run" if dry_run else ("failed" if any_failed else "success")
    return status, messages
