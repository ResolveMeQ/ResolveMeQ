from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("workflows", "0005_workflowstep_step_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="workflowstep",
            name="assignee_role",
            field=models.CharField(
                blank=True,
                choices=[
                    ("", "Anyone"),
                    ("it", "IT Support"),
                    ("hr", "HR"),
                    ("facilities", "Facilities"),
                    ("security", "Security"),
                ],
                default="",
                help_text="Only members with matching Profile.ops_role (or workspace owner) can claim.",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="workflow",
            name="due_at",
            field=models.DateTimeField(
                blank=True,
                help_text="Workflow-level SLA deadline (sum of template step due_days at start).",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="workflow",
            name="sla_breached_notified_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
