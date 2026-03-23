import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("base", "0017_trial_plan_and_trial_ends_at"),
        ("tickets", "0004_resolutiontemplate"),
    ]

    operations = [
        migrations.AddField(
            model_name="ticket",
            name="team",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="tickets",
                to="base.team",
                help_text="Workspace/team this ticket belongs to (from creator's active team when set).",
            ),
        ),
        migrations.AddIndex(
            model_name="ticket",
            index=models.Index(fields=["team", "status"], name="tickets_ticket_team_status_idx"),
        ),
    ]
