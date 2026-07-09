import uuid

from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


class WorkflowTemplate(models.Model):
    """
    A fixed, admin-authored/seeded sequence of steps. Never LLM-generated --
    templates are the curated alternative to freely inventing a multi-step
    process per ticket (same reasoning as excluding security_incident from
    remediation_script generation: curated beats free-form once the blast
    radius spans more than one person).
    """

    name = models.CharField(max_length=200)
    trigger_category = models.CharField(
        max_length=30,
        blank=True,
        help_text="Matches Ticket.category to auto-start this template on ticket creation. "
                   "Blank means this template is only ever started manually (standalone).",
    )
    team = models.ForeignKey(
        "base.Team",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="workflow_templates",
        help_text="Null means a global template available to every team (platform-seeded baseline), "
                   "same convention as KnowledgeBaseArticle.team.",
    )
    steps = models.JSONField(
        default=list,
        help_text='[{"title": "...", "description": "...", "assignee_team": "IT Support", "due_days": 2}, ...] '
                  "in order -- a flat list is enough for v1's strictly-sequential, no-branching shape. "
                  "Optional due_days (default 2) sets step due_at when the step becomes active.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Workflow(models.Model):
    STATUS_CHOICES = [
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket = models.ForeignKey(
        "tickets.Ticket",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="workflows",
        help_text="Null for a standalone workflow (started with no ticket).",
    )
    template = models.ForeignKey(
        WorkflowTemplate, on_delete=models.SET_NULL, null=True, blank=True, related_name="workflows"
    )
    team = models.ForeignKey(
        "base.Team", on_delete=models.SET_NULL, null=True, blank=True, related_name="workflows"
    )
    started_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="started_workflows"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="in_progress")
    due_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Workflow-level SLA deadline (sum of template step due_days at start).",
    )
    sla_breached_notified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.template.name if self.template_id else 'Workflow'} ({self.status})"


class WorkflowStep(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("active", "Active"),
        ("done", "Done"),
        ("skipped", "Skipped"),
    ]

    workflow = models.ForeignKey(Workflow, on_delete=models.CASCADE, related_name="steps")
    order_index = models.PositiveIntegerField()
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    assignee_team = models.CharField(
        max_length=100,
        blank=True,
        help_text="Display label for the assignee group (e.g. 'IT Support').",
    )
    ASSIGNEE_ROLE_CHOICES = [
        ("", "Anyone"),
        ("it", "IT Support"),
        ("hr", "HR"),
        ("facilities", "Facilities"),
        ("security", "Security"),
    ]
    assignee_role = models.CharField(
        max_length=20,
        choices=ASSIGNEE_ROLE_CHOICES,
        blank=True,
        default="",
        help_text="Only members with matching Profile.ops_role (or workspace owner) can claim.",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    claimed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="claimed_workflow_steps"
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    due_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Set when this step becomes active; derived from template due_days.",
    )
    auto_complete = models.BooleanField(
        default=False,
        help_text="Copied from the template at creation time. If set, this step is marked done "
                   "the instant it becomes active -- no human interaction (e.g. a pure log/notify "
                   "checkpoint). Not an external action -- just workflow bookkeeping.",
    )
    AUTO_ASSIGN_CHOICES = [
        ("", "None"),
        ("started_by", "Whoever started the workflow"),
        ("ticket_reporter", "The linked ticket's reporter"),
    ]
    auto_assign = models.CharField(
        max_length=20,
        choices=AUTO_ASSIGN_CHOICES,
        blank=True,
        help_text="Copied from the template at creation time. If set, claimed_by is resolved "
                   "automatically when this step becomes active, skipping the manual Claim click.",
    )
    STEP_TYPE_CHOICES = [
        ("manual", "Manual"),
        ("approval", "Approval"),
        ("auto_check", "Auto check"),
    ]
    step_type = models.CharField(
        max_length=20,
        choices=STEP_TYPE_CHOICES,
        default="manual",
        help_text="Copied from template at creation. Approval steps use an Approve action in UI.",
    )
    child_ticket = models.ForeignKey(
        "tickets.Ticket",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="spawned_from_workflow_steps",
        help_text="Child ticket spawned when this step became active (P3-4).",
    )

    class Meta:
        ordering = ["order_index"]

    def __str__(self):
        return f"{self.title} ({self.status})"


class WorkflowStepAssistantEvent(models.Model):
    """Telemetry for workflow step AI assistant (P3-1)."""

    EVENT_VIEWED = "viewed"
    EVENT_ACCEPTED = "accepted"
    EVENT_CHOICES = [
        (EVENT_VIEWED, "Viewed"),
        (EVENT_ACCEPTED, "Accepted"),
    ]

    step = models.ForeignKey(
        WorkflowStep,
        on_delete=models.CASCADE,
        related_name="assistant_events",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="workflow_step_assistant_events",
    )
    event_type = models.CharField(max_length=16, choices=EVENT_CHOICES)
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["step", "event_type", "created_at"]),
        ]

    def __str__(self):
        return f"{self.event_type} step={self.step_id} user={self.user_id}"

