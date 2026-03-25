# Generated manually for outcome metrics and confidence logging

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tickets", "0006_remove_ticket_tickets_ticket_team_status_idx_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="ticket",
            name="first_ai_at",
            field=models.DateTimeField(
                blank=True,
                help_text="When the ticket first received AI output (analyze task or first AI chat message).",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="ticket",
            name="escalated_at",
            field=models.DateTimeField(
                blank=True,
                help_text="When the ticket first moved to escalated status.",
                null=True,
            ),
        ),
        migrations.CreateModel(
            name="AgentConfidenceLog",
            fields=[
                ("id", models.AutoField(primary_key=True, serialize=False)),
                (
                    "source",
                    models.CharField(
                        choices=[("analyze", "Analyze"), ("chat", "Chat")],
                        db_index=True,
                        max_length=20,
                    ),
                ),
                ("confidence", models.FloatField(blank=True, null=True)),
                (
                    "recommended_action",
                    models.CharField(blank=True, default="", max_length=120),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "ticket",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="confidence_logs",
                        to="tickets.ticket",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="agentconfidencelog",
            index=models.Index(
                fields=["ticket", "created_at"], name="tickets_age_ticket_i_7b8c9d_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="agentconfidencelog",
            index=models.Index(
                fields=["source", "created_at"], name="tickets_age_source_i_8c9d0e_idx"
            ),
        ),
    ]
