import uuid

from django.db import models


class ComplianceAuditEvent(models.Model):
    """
    Append-only compliance audit stream for security reviews and SOC2 prep.
    Records are immutable after insert.
    """

    EVENT_TYPES = [
        ("ticket.created", "Ticket created"),
        ("ticket.escalated", "Ticket escalated"),
        ("ticket.resolved", "Ticket resolved"),
        ("workflow.step.completed", "Workflow step completed"),
        ("rule.executed", "Rule executed"),
        ("rule.created", "Rule created"),
        ("rule.updated", "Rule updated"),
        ("rule.deleted", "Rule deleted"),
        ("msp.enabled", "MSP mode enabled"),
        ("msp.client_created", "MSP client created"),
        ("workspace.admin.granted", "Workspace admin granted"),
        ("workspace.admin.revoked", "Workspace admin revoked"),
        ("workspace.permissions.updated", "Workspace permissions updated"),
        ("audit.exported", "Audit log exported"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.ForeignKey(
        "base.Team",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="compliance_audit_events",
    )
    actor = models.ForeignKey(
        "base.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="compliance_audit_events",
    )
    actor_email = models.CharField(max_length=255, blank=True)
    event_type = models.CharField(max_length=64, choices=EVENT_TYPES)
    resource_type = models.CharField(max_length=64, blank=True)
    resource_id = models.CharField(max_length=128, blank=True)
    summary = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["team", "created_at"]),
            models.Index(fields=["event_type", "created_at"]),
        ]

    def save(self, *args, **kwargs):
        if self.pk and ComplianceAuditEvent.objects.filter(pk=self.pk).exists():
            raise ValueError("Compliance audit events are immutable.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Compliance audit events cannot be deleted.")

    def __str__(self):
        return f"{self.event_type} @ {self.created_at}"
