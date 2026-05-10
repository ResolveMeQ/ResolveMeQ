# Generated manually for subscription expiry notifications

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0023_profile_slack_identity'),
    ]

    operations = [
        migrations.AddField(
            model_name='subscription',
            name='subscription_expired_notified_at',
            field=models.DateTimeField(
                blank=True,
                help_text='When we sent the subscription expired email/in-app notice (at most once).',
                null=True,
            ),
        ),
    ]
