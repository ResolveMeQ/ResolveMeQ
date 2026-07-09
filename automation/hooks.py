"""Fire automation events from domain code without circular imports."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def _safe_dispatch(trigger: str, context: dict, **kwargs):
    try:
        from automation.engine import dispatch_event

        dispatch_event(trigger, context, **kwargs)
    except Exception as exc:
        logger.warning("Automation dispatch failed (%s): %s", trigger, exc)


def _safe_webhooks(trigger: str, context: dict):
    try:
        from integrations.notify import notify_webhook_event

        notify_webhook_event(trigger, context)
    except Exception as exc:
        logger.warning("Webhook fan-out failed (%s): %s", trigger, exc)


def _safe_jira_escalate(ticket):
    try:
        from integrations.jira_sync import maybe_sync_ticket_escalated_to_jira

        maybe_sync_ticket_escalated_to_jira(ticket)
    except Exception as exc:
        logger.warning("Jira escalate sync failed: %s", exc)


def _safe_jira_resolve(ticket):
    try:
        from integrations.jira_sync import maybe_sync_ticket_resolved_to_jira

        maybe_sync_ticket_resolved_to_jira(ticket)
    except Exception as exc:
        logger.warning("Jira resolve sync failed: %s", exc)


def on_ticket_created(ticket):
    ctx = {"ticket": ticket, "category": ticket.category, "status": ticket.status, "team_id": ticket.team_id}
    _safe_dispatch("ticket.created", ctx)
    _safe_webhooks("ticket.created", ctx)


def on_ticket_escalated(ticket):
    ctx = {"ticket": ticket, "category": ticket.category, "status": ticket.status, "team_id": ticket.team_id}
    _safe_dispatch("ticket.escalated", ctx)
    _safe_webhooks("ticket.escalated", ctx)
    _safe_jira_escalate(ticket)


def on_ticket_resolved(ticket):
    ctx = {"ticket": ticket, "category": ticket.category, "status": ticket.status, "team_id": ticket.team_id}
    _safe_dispatch("ticket.resolved", ctx)
    _safe_webhooks("ticket.resolved", ctx)
    _safe_jira_resolve(ticket)


def on_workflow_step_completed(workflow, step):
    ticket = workflow.ticket if workflow.ticket_id else None
    ctx = {
        "workflow": workflow,
        "step": step,
        "ticket": ticket,
        "team_id": workflow.team_id or (ticket.team_id if ticket else None),
    }
    _safe_dispatch("workflow.step.completed", ctx)
    _safe_webhooks("workflow.step.completed", ctx)
