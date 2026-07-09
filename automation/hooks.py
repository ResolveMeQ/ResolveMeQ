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


def _safe_audit(**kwargs):
    try:
        from monitoring.audit import record_audit_event

        record_audit_event(**kwargs)
    except Exception as exc:
        logger.warning("Compliance audit record failed: %s", exc)


def on_ticket_created(ticket):
    ctx = {"ticket": ticket, "category": ticket.category, "status": ticket.status, "team_id": ticket.team_id}
    _safe_dispatch("ticket.created", ctx)
    _safe_webhooks("ticket.created", ctx)
    _safe_audit(
        event_type="ticket.created",
        team=ticket.team,
        actor=getattr(ticket, "user", None),
        resource_type="ticket",
        resource_id=str(ticket.ticket_id),
        summary=f"Ticket #{ticket.ticket_id} created ({ticket.category or 'uncategorized'})",
        metadata={"category": ticket.category, "status": ticket.status},
    )


def on_ticket_escalated(ticket, actor=None):
    ctx = {"ticket": ticket, "category": ticket.category, "status": ticket.status, "team_id": ticket.team_id}
    _safe_dispatch("ticket.escalated", ctx)
    _safe_webhooks("ticket.escalated", ctx)
    _safe_jira_escalate(ticket)
    _safe_audit(
        event_type="ticket.escalated",
        team=ticket.team,
        actor=actor,
        resource_type="ticket",
        resource_id=str(ticket.ticket_id),
        summary=f"Ticket #{ticket.ticket_id} escalated",
        metadata={"category": ticket.category, "status": ticket.status},
    )


def on_ticket_resolved(ticket, actor=None):
    ctx = {"ticket": ticket, "category": ticket.category, "status": ticket.status, "team_id": ticket.team_id}
    _safe_dispatch("ticket.resolved", ctx)
    _safe_webhooks("ticket.resolved", ctx)
    _safe_jira_resolve(ticket)
    try:
        from workflows.child_tickets import maybe_complete_step_for_resolved_child

        maybe_complete_step_for_resolved_child(ticket)
    except Exception as exc:
        logger.warning("Child ticket workflow sync failed: %s", exc)
    _safe_audit(
        event_type="ticket.resolved",
        team=ticket.team,
        actor=actor,
        resource_type="ticket",
        resource_id=str(ticket.ticket_id),
        summary=f"Ticket #{ticket.ticket_id} resolved",
        metadata={"category": ticket.category, "status": ticket.status},
    )


def on_workflow_step_completed(workflow, step, actor=None):
    ticket = workflow.ticket if workflow.ticket_id else None
    ctx = {
        "workflow": workflow,
        "step": step,
        "ticket": ticket,
        "team_id": workflow.team_id or (ticket.team_id if ticket else None),
    }
    _safe_dispatch("workflow.step.completed", ctx)
    _safe_webhooks("workflow.step.completed", ctx)
    team = workflow.team or (ticket.team if ticket else None)
    _safe_audit(
        event_type="workflow.step.completed",
        team=team,
        actor=actor,
        resource_type="workflow_step",
        resource_id=str(step.id),
        summary=f"Workflow step completed: {step.title}",
        metadata={
            "workflow_id": str(workflow.id),
            "step_key": step.step_key,
            "ticket_id": ticket.ticket_id if ticket else None,
        },
    )
