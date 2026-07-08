from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("workflows", "0004_alter_workflowtemplate_steps"),
    ]

    operations = [
        migrations.AddField(
            model_name="workflowstep",
            name="step_type",
            field=models.CharField(
                choices=[
                    ("manual", "Manual"),
                    ("approval", "Approval"),
                    ("auto_check", "Auto check"),
                ],
                default="manual",
                help_text="Copied from template at creation. Approval steps show an Approve action in UI.",
                max_length=20,
            ),
        ),
    ]
