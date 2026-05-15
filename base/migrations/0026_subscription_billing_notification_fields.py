from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0025_subscription_grant_log'),
    ]

    operations = [
        migrations.AddField(
            model_name='subscription',
            name='subscription_welcome_notified_at',
            field=models.DateTimeField(
                blank=True,
                help_text='When we sent the subscription confirmed (welcome) notice.',
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='subscription',
            name='subscription_renewed_notified_period_end',
            field=models.DateTimeField(
                blank=True,
                help_text='Period end we last sent a renewal notice for (dedupes webhooks/payments).',
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='subscription',
            name='subscription_expiring_notified_for_end',
            field=models.DateTimeField(
                blank=True,
                help_text='Trial or period end date we sent an expiring-soon reminder for.',
                null=True,
            ),
        ),
    ]
