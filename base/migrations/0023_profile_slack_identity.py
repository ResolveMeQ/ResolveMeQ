from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("base", "0022_userpreferences_community_mentions"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="slack_user_id",
            field=models.CharField(
                blank=True,
                db_index=True,
                default="",
                help_text="Slack member ID (e.g. U123...) for DM and attribution; optional",
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="profile",
            name="slack_team_id",
            field=models.CharField(
                blank=True,
                db_index=True,
                default="",
                help_text="Slack workspace ID (T123...) this user is linked to; optional",
                max_length=32,
            ),
        ),
    ]

