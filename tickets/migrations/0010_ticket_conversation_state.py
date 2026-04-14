from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("tickets", "0009_rename_tickets_age_ticket_i_7b8c9d_idx_tickets_age_ticket__6d35d1_idx_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="ticket",
            name="awaiting_response_from",
            field=models.CharField(
                blank=True,
                choices=[("", "None"), ("support", "Support"), ("user", "User")],
                default="",
                help_text="Conversation owner for next response: support or user.",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="ticket",
            name="last_message_at",
            field=models.DateTimeField(
                blank=True,
                help_text="Timestamp of the latest comment/message in the support thread.",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="ticket",
            name="last_message_by",
            field=models.ForeignKey(
                blank=True,
                help_text="User who sent the latest comment/message.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="last_ticket_messages",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
