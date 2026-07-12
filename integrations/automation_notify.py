"""Deliver automation rule notify_slack / notify_teams actions."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

from django.conf import settings

logger = logging.getLogger(__name__)


def _team_from_context(ctx: Dict[str, Any]):
    ticket = ctx.get("ticket")
    workflow = ctx.get("workflow")
    if ticket and getattr(ticket, "team", None):
        return ticket.team
    if workflow and getattr(workflow, "team", None):
        return workflow.team
    return ctx.get("team")


def _default_message(ctx: Dict[str, Any]) -> str:
    ticket = ctx.get("ticket")
    workflow = ctx.get("workflow")
    step = ctx.get("step")
    parts = []
    if ticket:
        parts.append(f"Ticket #{ticket.ticket_id}: {ticket.issue_type or 'Support request'}")
        if ticket.category:
            parts.append(f"Category: {ticket.category}")
        if ticket.status:
            parts.append(f"Status: {ticket.status}")
    if workflow:
        parts.append(f"Workflow: {getattr(workflow, 'name', None) or workflow.id}")
    if step:
        parts.append(f"Step completed: {step.title}")
    return "\n".join(parts) if parts else "Automation rule fired."


def _frontend_ticket_url(ticket_id) -> str:
    base = getattr(settings, "FRONTEND_URL", "https://app.resolvemeq.net").rstrip("/")
    return f"{base}/tickets?highlight={ticket_id}"


def deliver_automation_slack(action: dict, ctx: Dict[str, Any], *, dry_run: bool = False) -> Tuple[bool, str]:
    from integrations import slack_installation as slack_inst

    ticket = ctx.get("ticket")
    team = _team_from_context(ctx)
    message = (action.get("message") or "").strip() or _default_message(ctx)
    title = (action.get("title") or "").strip() or "ResolveMeQ automation"
    channel = (action.get("channel_id") or "").strip()
    if not channel:
        channel = (
            getattr(settings, "SLACK_ESCALATION_ALERT_CHANNEL", "") or ""
        ).strip() or (getattr(settings, "SLACK_ESCALATION_CHANNEL", "") or "").strip()

    if dry_run:
        target = channel or "ops channel (from settings)"
        return True, f"Would post Slack message to {target}."

    if ticket and not (action.get("channel_id") or "").strip():
        from integrations.views import notify_support_escalation_slack

        notify_support_escalation_slack(
            ticket,
            {
                "conversation_summary": message,
                "priority": (action.get("priority") or "medium"),
            },
        )
        return True, "Posted Slack ops notification for ticket."

    inst = slack_inst.get_installation_for_team(team)
    if not inst:
        return False, "No active Slack workspace connected for this team."
    if not channel:
        return False, "No Slack channel configured (set channel_id or SLACK_ESCALATION_CHANNEL)."

    blocks = [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*{title}*\n{message}"},
        },
    ]
    if ticket:
        blocks.append({
            "type": "actions",
            "elements": [{
                "type": "button",
                "text": {"type": "plain_text", "text": "View ticket"},
                "url": _frontend_ticket_url(ticket.ticket_id),
            }],
        })
    payload = {
        "channel": channel,
        "text": f"{title}: {message[:200]}",
        "blocks": blocks,
    }
    resp = slack_inst.slack_api_post(inst, "chat.postMessage", payload)
    if resp:
        return True, f"Posted Slack message to channel {channel}."
    return False, "Slack API call failed."


def deliver_automation_teams(action: dict, ctx: Dict[str, Any], *, dry_run: bool = False) -> Tuple[bool, str]:
    ticket = ctx.get("ticket")
    message = (action.get("message") or "").strip() or _default_message(ctx)

    if dry_run:
        return True, "Would post Microsoft Teams notification."

    if ticket:
        from integrations.teams_views import notify_support_escalation_teams

        notify_support_escalation_teams(
            ticket,
            {
                "conversation_summary": message,
                "priority": (action.get("priority") or "medium"),
            },
        )
        return True, "Posted Teams ops notification for ticket."

    workflow = ctx.get("workflow")
    step = ctx.get("step")
    if workflow and step:
        from integrations.teams_views import notify_workflow_step_active

        notify_workflow_step_active(workflow, step)
        return True, "Notified Teams assignees for active workflow step."

    return False, "Teams notify requires a ticket or workflow step in context."


def deliver_automation_notify(action: dict, ctx: Dict[str, Any], *, provider: str, dry_run: bool = False) -> Tuple[bool, str]:
    if provider == "slack":
        return deliver_automation_slack(action, ctx, dry_run=dry_run)
    if provider == "teams":
        return deliver_automation_teams(action, ctx, dry_run=dry_run)
    return False, f"Unknown notify provider: {provider}"
