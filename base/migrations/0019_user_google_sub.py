# Generated manually: Google Sign-In linking

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("base", "0018_supportcontactsubmission"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="google_sub",
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text="Stable Google account id (sub claim) when the user signs in with Google",
                max_length=255,
                null=True,
                unique=True,
                verbose_name="Google subject",
            ),
        ),
    ]
