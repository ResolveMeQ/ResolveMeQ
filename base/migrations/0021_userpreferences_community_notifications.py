from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("base", "0020_plan_agent_usage_monthly"),
    ]

    operations = [
        migrations.AddField(
            model_name="userpreferences",
            name="community_answers",
            field=models.BooleanField(
                default=True,
                help_text="Notify when your community questions or answers receive new answers/acceptance updates",
                verbose_name="community answers",
            ),
        ),
        migrations.AddField(
            model_name="userpreferences",
            name="community_comments",
            field=models.BooleanField(
                default=True,
                help_text="Notify when your community threads receive new comments",
                verbose_name="community comments",
            ),
        ),
        migrations.AddField(
            model_name="userpreferences",
            name="community_new_questions",
            field=models.BooleanField(
                default=True,
                help_text="Notify when new community questions are posted in your workspace",
                verbose_name="community new questions",
            ),
        ),
    ]
