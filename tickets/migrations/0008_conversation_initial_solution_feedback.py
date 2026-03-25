from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tickets", "0007_ticket_first_ai_escalated_at_agentconfidencelog"),
    ]

    operations = [
        migrations.AddField(
            model_name="conversation",
            name="initial_solution_was_helpful",
            field=models.BooleanField(
                blank=True,
                help_text="True=helpful, False=not helpful, None=not yet rated (injected analyze block).",
                null=True,
            ),
        ),
    ]
