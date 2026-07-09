"""Automation rules — triggers, conditions, and actions (Phase 2)."""

VALID_TRIGGERS = frozenset({
    "ticket.created",
    "ticket.escalated",
    "ticket.resolved",
    "workflow.step.completed",
    "schedule.cron",
})

VALID_CONDITION_OPS = frozenset({"equals", "not_equals", "in"})

VALID_ACTION_TYPES = frozenset({
    "start_workflow",
    "assign_ticket",
    "notify_slack",
    "notify_teams",
    "set_field",
    "call_webhook",
    "run_agent",
})

TRIGGER_LABELS = {
    "ticket.created": "Ticket created",
    "ticket.escalated": "Ticket escalated",
    "ticket.resolved": "Ticket resolved",
    "workflow.step.completed": "Workflow step completed",
    "schedule.cron": "Scheduled (cron)",
}

ACTION_LABELS = {
    "start_workflow": "Start workflow from template",
    "assign_ticket": "Assign ticket to user",
    "notify_slack": "Notify Slack",
    "notify_teams": "Notify Microsoft Teams",
    "set_field": "Set ticket field",
    "call_webhook": "Call webhook",
    "run_agent": "Run AI agent on ticket",
}
