from django.db import models


class Rule(models.Model):
    """When trigger fires and conditions match, run actions in order."""

    TRIGGER_CHOICES = [(t, t) for t in sorted([
        "ticket.created",
        "ticket.escalated",
        "ticket.resolved",
        "workflow.step.completed",
        "schedule.cron",
    ])]

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    team = models.ForeignKey(
        "base.Team",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="automation_rules",
        help_text="Null = global rule (platform-seeded defaults).",
    )
    trigger = models.CharField(max_length=50, choices=TRIGGER_CHOICES)
    conditions = models.JSONField(
        default=list,
        blank=True,
        help_text='AND list, e.g. [{"field": "category", "op": "equals", "value": "onboarding"}]',
    )
    actions = models.JSONField(
        default=list,
        help_text='e.g. [{"type": "start_workflow", "template_trigger_category": "onboarding"}]',
    )
    is_active = models.BooleanField(default=True)
    priority = models.PositiveIntegerField(
        default=100,
        help_text="Lower numbers run first.",
    )
    cron_expression = models.CharField(
        max_length=100,
        blank=True,
        help_text=(
            "5-field cron expression, UTC (e.g. '0 9 * * 1' = every Monday 09:00 UTC). "
            "Required when trigger is schedule.cron."
        ),
    )
    cron_last_fired_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Set by the cron dispatcher; prevents firing twice for the same due minute.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["priority", "name"]

    def __str__(self):
        scope = self.team.name if self.team_id else "global"
        return f"{self.name} ({self.trigger}, {scope})"


class RuleExecutionLog(models.Model):
    STATUS_CHOICES = [
        ("success", "Success"),
        ("skipped", "Skipped"),
        ("failed", "Failed"),
        ("dry_run", "Dry run"),
    ]

    rule = models.ForeignKey(
        Rule,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="execution_logs",
    )
    trigger = models.CharField(max_length=50)
    team = models.ForeignKey(
        "base.Team",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rule_execution_logs",
    )
    ticket = models.ForeignKey(
        "tickets.Ticket",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rule_execution_logs",
    )
    workflow = models.ForeignKey(
        "workflows.Workflow",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rule_execution_logs",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    message = models.TextField(blank=True)
    actions_planned = models.JSONField(default=list, blank=True)
    context_snapshot = models.JSONField(default=dict, blank=True)
    executed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-executed_at"]

    def __str__(self):
        return f"{self.trigger} / {self.status} @ {self.executed_at}"


# Legacy stub — kept for migration compatibility; unused by rules engine.
class AutomationTask(models.Model):
    task_id = models.AutoField(primary_key=True)
    command = models.CharField(max_length=100)
    parameters = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=50)
    result = models.TextField(blank=True)
    executed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.command} ({self.status})"
