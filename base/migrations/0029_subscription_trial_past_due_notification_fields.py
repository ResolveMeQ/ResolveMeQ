from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0028_teams_integration'),
    ]

    operations = [
        migrations.AddField(
            model_name='subscription',
            name='subscription_trial_started_notified_at',
            field=models.DateTimeField(
                blank=True,
                help_text='When we sent the free-trial-started notice (signup trial only).',
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='subscription',
            name='subscription_past_due_notified_for_period_end',
            field=models.DateTimeField(
                blank=True,
                help_text='Billing period end we last sent a payment-failed / past-due notice for.',
                null=True,
            ),
        ),
    ]
