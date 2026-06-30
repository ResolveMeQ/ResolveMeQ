from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tickets", "0012_chatmessage_agent_sender"),
    ]

    operations = [
        migrations.AddField(
            model_name="ticket",
            name="slack_thread_ts",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Root Slack DM thread timestamp for threaded replies to this ticket's reporter.",
                max_length=50,
            ),
        ),
    ]
