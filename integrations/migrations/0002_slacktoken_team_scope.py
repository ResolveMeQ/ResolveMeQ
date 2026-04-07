# Slack workspace ↔ ResolveMeQ team linkage

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("integrations", "0001_initial"),
        ("base", "0020_plan_agent_usage_monthly"),
    ]

    operations = [
        migrations.AlterField(
            model_name="slacktoken",
            name="access_token",
            field=models.TextField(help_text="Slack bot token (xoxb-...)"),
        ),
        migrations.AlterField(
            model_name="slacktoken",
            name="team_id",
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text="Slack workspace ID (T...)",
                max_length=32,
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="slacktoken",
            name="bot_user_id",
            field=models.CharField(blank=True, max_length=32, null=True),
        ),
        migrations.AddField(
            model_name="slacktoken",
            name="is_active",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="slacktoken",
            name="updated_at",
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
        migrations.AlterField(
            model_name="slacktoken",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AddField(
            model_name="slacktoken",
            name="installed_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="slack_app_installs",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="slacktoken",
            name="resolvemeq_team",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="slack_installations",
                to="base.team",
            ),
        ),
        migrations.AddConstraint(
            model_name="slacktoken",
            constraint=models.UniqueConstraint(
                condition=models.Q(team_id__isnull=False),
                fields=("team_id",),
                name="integrations_slacktoken_unique_slack_team_id",
            ),
        ),
        migrations.AddIndex(
            model_name="slacktoken",
            index=models.Index(
                fields=["resolvemeq_team", "is_active"],
                name="integslack_team_active_idx",
            ),
        ),
    ]
