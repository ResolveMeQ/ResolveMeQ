from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("monitoring", "0002_workspace_admin_audit_events"),
    ]

    operations = [
        migrations.AlterField(
            model_name="complianceauditevent",
            name="event_type",
            field=models.CharField(
                choices=[
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
                ],
                max_length=64,
            ),
        ),
    ]
