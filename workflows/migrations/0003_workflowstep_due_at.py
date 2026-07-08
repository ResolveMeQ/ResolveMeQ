from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("workflows", "0002_workflowstep_auto_assign_workflowstep_auto_complete"),
    ]

    operations = [
        migrations.AddField(
            model_name="workflowstep",
            name="due_at",
            field=models.DateTimeField(
                blank=True,
                help_text="Set when this step becomes active; derived from template due_days.",
                null=True,
            ),
        ),
    ]
