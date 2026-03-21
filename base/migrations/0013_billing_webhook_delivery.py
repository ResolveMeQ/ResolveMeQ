# Generated manually for Dodo webhook idempotency

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0012_plan_gateway_product_subscription_gateway'),
    ]

    operations = [
        migrations.CreateModel(
            name='BillingWebhookDelivery',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('delivery_id', models.CharField(max_length=255, unique=True)),
                ('provider', models.CharField(choices=[('dodo', 'Dodo Payments')], max_length=32)),
                ('event_type', models.CharField(max_length=128)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Billing webhook delivery',
                'verbose_name_plural': 'Billing webhook deliveries',
                'ordering': ['-created_at'],
            },
        ),
    ]
