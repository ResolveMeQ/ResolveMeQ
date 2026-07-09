"""Rules engine: match triggers, evaluate conditions, execute actions, log results."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from django.db.models import Q

from .actions import execute_actions
from .conditions import evaluate_conditions
from .constants import VALID_TRIGGERS
from .models import Rule, RuleExecutionLog

logger = logging.getLogger(__name__)


def _team_id_from_context(ctx: Dict[str, Any]) -> Optional[str]:
    if ctx.get("team_id"):
        return str(ctx["team_id"])
    ticket = ctx.get("ticket")
    if ticket and ticket.team_id:
        return str(ticket.team_id)
    workflow = ctx.get("workflow")
    if workflow and workflow.team_id:
        return str(workflow.team_id)
    team = ctx.get("team")
    if team:
        return str(team.pk)
    return None


def _snapshot_context(ctx: Dict[str, Any]) -> dict:
    ticket = ctx.get("ticket")
    workflow = ctx.get("workflow")
    step = ctx.get("step")
    out: Dict[str, Any] = {}
    if ticket:
        out["ticket_id"] = ticket.ticket_id
        out["category"] = ticket.category
        out["status"] = ticket.status
    if workflow:
        out["workflow_id"] = str(workflow.id)
        out["workflow_status"] = workflow.status
    if step:
        out["step_id"] = step.id
        out["step_title"] = step.title
    return out


def rules_queryset_for_team(team_id: Optional[str]):
    qs = Rule.objects.filter(is_active=True)
    if team_id:
        qs = qs.filter(Q(team_id=team_id) | Q(team__isnull=True))
    else:
        qs = qs.filter(team__isnull=True)
    return qs


def dispatch_event(
    trigger: str,
    context: Dict[str, Any],
    *,
    dry_run: bool = False,
    rule_id: Optional[int] = None,
) -> list:
    """
    Find matching rules and run actions. Returns list of log ids created.
    If rule_id is set, only that rule is evaluated (for admin test).
    """
    if trigger not in VALID_TRIGGERS:
        logger.warning("Unknown automation trigger: %s", trigger)
        return []
    if trigger == "schedule.cron":
        logger.debug("schedule.cron not implemented in v1 executor.")
        return []

    team_id = _team_id_from_context(context)
    if rule_id:
        qs = Rule.objects.filter(pk=rule_id, is_active=True)
    else:
        qs = rules_queryset_for_team(team_id).filter(trigger=trigger)

    log_ids = []
    for rule in qs.order_by("priority", "id"):
        if not evaluate_conditions(rule.conditions, context):
            if rule_id:
                log = RuleExecutionLog.objects.create(
                    rule=rule,
                    trigger=trigger,
                    team_id=team_id,
                    ticket=context.get("ticket"),
                    workflow=context.get("workflow"),
                    status="skipped",
                    message="Conditions did not match.",
                    actions_planned=rule.actions,
                    context_snapshot=_snapshot_context(context),
                )
                log_ids.append(log.id)
            continue

        status, messages = execute_actions(rule.actions, context, dry_run=dry_run)
        log = RuleExecutionLog.objects.create(
            rule=rule,
            trigger=trigger,
            team_id=team_id or rule.team_id,
            ticket=context.get("ticket"),
            workflow=context.get("workflow"),
            status=status,
            message=" | ".join(messages),
            actions_planned=rule.actions,
            context_snapshot=_snapshot_context(context),
        )
        log_ids.append(log.id)
        if not dry_run:
            try:
                from base.models import Team
                from monitoring.audit import record_audit_event

                team_obj = None
                tid = team_id or rule.team_id
                if tid:
                    team_obj = Team.objects.filter(pk=tid).first()
                record_audit_event(
                    event_type="rule.executed",
                    team=team_obj,
                    resource_type="rule",
                    resource_id=str(rule.id),
                    summary=f"Rule executed: {rule.name} ({status})",
                    metadata={
                        "trigger": trigger,
                        "status": status,
                        "log_id": log.id,
                    },
                )
            except Exception as exc:
                logger.warning("Compliance audit for rule execution failed: %s", exc)
        if rule_id:
            break

    return log_ids
