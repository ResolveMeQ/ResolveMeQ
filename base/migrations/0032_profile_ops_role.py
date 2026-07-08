from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("base", "0031_blogpost"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="ops_role",
            field=models.CharField(
                blank=True,
                choices=[
                    ("", "General"),
                    ("it", "IT Support"),
                    ("hr", "HR"),
                    ("facilities", "Facilities"),
                    ("security", "Security"),
                ],
                default="",
                help_text="Workflow step claim routing — which playbook steps this user can claim.",
                max_length=20,
            ),
        ),
    ]
