from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("base", "0021_userpreferences_community_notifications"),
    ]

    operations = [
        migrations.AddField(
            model_name="userpreferences",
            name="community_mentions",
            field=models.BooleanField(
                default=True,
                help_text="Notify when someone @mentions you in community Q&A",
                verbose_name="community mentions",
            ),
        ),
    ]

